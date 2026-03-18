"""
Summary service — orchestrates data gathering from Supabase and summary report generation.

Gathers period data, calls the summary agent, and stores results.
"""

import logging
from datetime import date, timedelta

import httpx

from src.config.settings import settings
from src.models.database import get_company_by_ticker
from src.services.supabase_client import get_supabase_client

logger = logging.getLogger("mreit-monitor.summary_service")


def _gather_period_data(
    company_id: str,
    start_date: date,
    end_date: date,
) -> dict:
    """
    Query all relevant data for a date range from Supabase.

    Returns dict with keys: monthly_data, quarterly_data, analyses,
    portfolio_data, cpr_data
    """
    client = get_supabase_client()

    start_str = start_date.isoformat()
    end_str = end_date.isoformat()

    # Monthly metrics
    monthly_data = (
        client.table("monthly_metrics_ML_REIT")
        .select("*")
        .eq("company_id", company_id)
        .gte("as_of_date", start_str)
        .lte("as_of_date", end_str)
        .order("as_of_date", desc=False)
        .execute()
    ).data

    # Quarterly metrics
    quarterly_data = (
        client.table("quarterly_metrics_ML_REIT")
        .select("*")
        .eq("company_id", company_id)
        .gte("period_end_date", start_str)
        .lte("period_end_date", end_str)
        .order("period_end_date", desc=False)
        .execute()
    ).data

    # Agent analyses from this period
    analyses = (
        client.table("agent_analyses_ML_REIT")
        .select("*")
        .eq("company_id", company_id)
        .gte("created_at", start_str)
        .lte("created_at", end_str + "T23:59:59")
        .order("created_at", desc=False)
        .execute()
    ).data

    # Portfolio positions — get filing IDs for the period first
    filings_in_period = (
        client.table("filings_ML_REIT")
        .select("id")
        .eq("company_id", company_id)
        .gte("filing_date", start_str)
        .lte("filing_date", end_str)
        .execute()
    ).data
    filing_ids = [f["id"] for f in filings_in_period]

    portfolio_data = []
    if filing_ids:
        portfolio_data = (
            client.table("portfolio_positions_ML_REIT")
            .select("*")
            .in_("filing_id", filing_ids)
            .execute()
        ).data

    # CPR data
    cpr_data = (
        client.table("cpr_data_ML_REIT")
        .select("*")
        .eq("company_id", company_id)
        .gte("month", start_str)
        .lte("month", end_str)
        .order("month", desc=False)
        .execute()
    ).data

    # Universal extractions (multi-company pipeline)
    universal_data = _gather_universal_data(company_id, start_date, end_date)

    return {
        "monthly_data": monthly_data,
        "quarterly_data": quarterly_data,
        "analyses": analyses,
        "portfolio_data": portfolio_data,
        "cpr_data": cpr_data,
        "universal_extractions": universal_data,
    }


def _gather_universal_data(
    company_id: str,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """
    Query universal_extractions for a company in a date range.
    Returns list of extraction_data JSONB objects joined with document metadata.
    """
    client = get_supabase_client()
    start_str = start_date.isoformat()
    end_str = end_date.isoformat()

    try:
        result = (
            client.table("universal_extractions_ML_REIT")
            .select("*, company_documents(document_type, document_date, title, source_url)")
            .eq("company_id", company_id)
            .gte("period_end", start_str)
            .lte("period_end", end_str)
            .order("period_end", desc=False)
            .execute()
        )
        return result.data
    except Exception:
        # Table may not exist yet during transition
        return []


def _gather_prior_period_data(
    company_id: str,
    current_period_start: date,
    report_type: str,
) -> dict:
    """
    Query prior period data for period-over-period comparison in summary reports.

    Lookback by report_type:
    - monthly: 3 prior months of monthly_metrics + portfolio_positions
    - quarterly: prior quarter's quarterly_metrics + last month's positions
    - annual: prior year's 4 quarterly_metrics + December positions
    """
    client = get_supabase_client()

    if report_type == "monthly":
        filing_limit = 3
        lookback_start = current_period_start - timedelta(days=100)
    elif report_type == "quarterly":
        filing_limit = 3
        lookback_start = current_period_start - timedelta(days=100)
    else:  # annual
        filing_limit = 12
        lookback_start = current_period_start - timedelta(days=400)

    lookback_str = lookback_start.isoformat()
    current_str = current_period_start.isoformat()

    # Prior monthly metrics
    prior_monthly = (
        client.table("monthly_metrics_ML_REIT")
        .select("*")
        .eq("company_id", company_id)
        .gte("as_of_date", lookback_str)
        .lt("as_of_date", current_str)
        .order("as_of_date", desc=True)
        .limit(filing_limit)
        .execute()
    ).data

    # Prior quarterly metrics
    quarterly_limit = 1 if report_type == "monthly" else 4
    prior_quarterly = (
        client.table("quarterly_metrics_ML_REIT")
        .select("*")
        .eq("company_id", company_id)
        .gte("period_end_date", lookback_str)
        .lt("period_end_date", current_str)
        .order("period_end_date", desc=True)
        .limit(quarterly_limit)
        .execute()
    ).data

    # Prior portfolio positions — get filing IDs for monthly_update filings before the period
    prior_filings = (
        client.table("filings_ML_REIT")
        .select("id, filing_date")
        .eq("company_id", company_id)
        .eq("filing_type", "monthly_update")
        .gte("filing_date", lookback_str)
        .lt("filing_date", current_str)
        .order("filing_date", desc=True)
        .limit(filing_limit)
        .execute()
    ).data

    prior_filing_ids = [f["id"] for f in prior_filings]

    prior_positions = {}
    if prior_filing_ids:
        all_positions = (
            client.table("portfolio_positions_ML_REIT")
            .select("*")
            .in_("filing_id", prior_filing_ids)
            .execute()
        ).data

        # Group by as_of_date
        for pos in all_positions:
            as_of = pos.get("as_of_date", "unknown")
            if as_of not in prior_positions:
                prior_positions[as_of] = []
            prior_positions[as_of].append(pos)

    # Prior universal extractions
    prior_universal = _gather_universal_data(company_id, lookback_start, current_period_start - timedelta(days=1))

    return {
        "prior_monthly_metrics": prior_monthly,
        "prior_portfolio_positions": prior_positions,
        "prior_quarterly_metrics": prior_quarterly,
        "prior_universal_extractions": prior_universal,
    }


def _store_summary_report(
    company_id: str,
    report_type: str,
    period_label: str,
    period_start: date,
    period_end: date,
    report_json: dict,
    model_used: str,
    tokens_used: int,
) -> dict:
    """Upsert a summary report into the summary_reports table."""
    client = get_supabase_client()

    row = {
        "company_id": company_id,
        "report_type": report_type,
        "period_label": period_label,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "report_json": report_json,
        "model_used": model_used,
        "tokens_used": tokens_used,
    }

    result = (
        client.table("summary_reports_ML_REIT")
        .upsert(row, on_conflict="company_id,report_type,period_start")
        .execute()
    )
    return result.data[0] if result.data else row


async def _fire_webhook(
    report_id: str,
    ticker: str,
    company_name: str,
    report_type: str,
    period_label: str,
    report_json: dict,
) -> None:
    """POST to the configured webhook URL. Fire-and-forget — never raises."""
    if not settings.webhook_url:
        return

    overall = (report_json.get("overall_summary", {}).get("content") or "")[:500]
    payload = {
        "secret": settings.webhook_secret,
        "report_id": report_id,
        "company_ticker": ticker,
        "company_name": company_name,
        "report_type": report_type,
        "period_label": period_label,
        "overall_summary": overall,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(settings.webhook_url, json=payload)
            logger.info("Webhook sent for %s %s (status=%d)", ticker, period_label, resp.status_code)
    except Exception as e:
        logger.warning("Webhook failed for %s %s: %s", ticker, period_label, e)


async def generate_monthly_summary(
    company_id: str,
    company_name: str,
    ticker: str,
    year: int,
    month: int,
) -> dict:
    """
    Generate a monthly summary report.

    Gathers that month's data and calls the summary agent.
    Returns the stored summary report row.
    """
    from src.agents.summary_agent import generate_summary_report

    # Period is the full month
    period_start = date(year, month, 1)
    if month == 12:
        period_end = date(year, 12, 31)
    else:
        period_end = date(year, month + 1, 1) - timedelta(days=1)

    period_label = period_start.strftime("%B %Y")

    logger.info("Generating monthly summary for %s %s", ticker, period_label)

    data_context = _gather_period_data(company_id, period_start, period_end)
    prior_context = _gather_prior_period_data(company_id, period_start, "monthly")
    data_context.update(prior_context)

    report, metadata = await generate_summary_report(
        company_name=company_name,
        ticker=ticker,
        period_label=period_label,
        report_type="monthly",
        data_context=data_context,
    )

    stored = _store_summary_report(
        company_id=company_id,
        report_type="monthly",
        period_label=period_label,
        period_start=period_start,
        period_end=period_end,
        report_json=report.model_dump(),
        model_used=metadata["model"],
        tokens_used=metadata.get("input_tokens", 0) + metadata.get("output_tokens", 0),
    )

    logger.info("Monthly summary stored for %s %s", ticker, period_label)
    await _fire_webhook(stored.get("id", ""), ticker, company_name, "monthly", period_label, report.model_dump())
    return stored


async def generate_quarterly_summary(
    company_id: str,
    company_name: str,
    ticker: str,
    year: int,
    quarter: int,
) -> dict:
    """Generate a quarterly summary covering 3 months + any quarterly filings."""
    from src.agents.summary_agent import generate_summary_report

    quarter_starts = {1: 1, 2: 4, 3: 7, 4: 10}
    start_month = quarter_starts[quarter]
    period_start = date(year, start_month, 1)

    end_month = start_month + 2
    if end_month == 12:
        period_end = date(year, 12, 31)
    else:
        period_end = date(year, end_month + 1, 1) - timedelta(days=1)

    period_label = f"Q{quarter} {year}"

    logger.info("Generating quarterly summary for %s %s", ticker, period_label)

    data_context = _gather_period_data(company_id, period_start, period_end)
    prior_context = _gather_prior_period_data(company_id, period_start, "quarterly")
    data_context.update(prior_context)

    report, metadata = await generate_summary_report(
        company_name=company_name,
        ticker=ticker,
        period_label=period_label,
        report_type="quarterly",
        data_context=data_context,
    )

    stored = _store_summary_report(
        company_id=company_id,
        report_type="quarterly",
        period_label=period_label,
        period_start=period_start,
        period_end=period_end,
        report_json=report.model_dump(),
        model_used=metadata["model"],
        tokens_used=metadata.get("input_tokens", 0) + metadata.get("output_tokens", 0),
    )

    logger.info("Quarterly summary stored for %s %s", ticker, period_label)
    await _fire_webhook(stored.get("id", ""), ticker, company_name, "quarterly", period_label, report.model_dump())
    return stored


async def generate_annual_summary(
    company_id: str,
    company_name: str,
    ticker: str,
    year: int,
) -> dict:
    """Generate an annual summary covering 12 months + all quarterly data."""
    from src.agents.summary_agent import generate_summary_report

    period_start = date(year, 1, 1)
    period_end = date(year, 12, 31)
    period_label = f"FY {year}"

    logger.info("Generating annual summary for %s %s", ticker, period_label)

    data_context = _gather_period_data(company_id, period_start, period_end)
    prior_context = _gather_prior_period_data(company_id, period_start, "annual")
    data_context.update(prior_context)

    report, metadata = await generate_summary_report(
        company_name=company_name,
        ticker=ticker,
        period_label=period_label,
        report_type="annual",
        data_context=data_context,
    )

    stored = _store_summary_report(
        company_id=company_id,
        report_type="annual",
        period_label=period_label,
        period_start=period_start,
        period_end=period_end,
        report_json=report.model_dump(),
        model_used=metadata["model"],
        tokens_used=metadata.get("input_tokens", 0) + metadata.get("output_tokens", 0),
    )

    logger.info("Annual summary stored for %s %s", ticker, period_label)
    await _fire_webhook(stored.get("id", ""), ticker, company_name, "annual", period_label, report.model_dump())
    return stored


async def analyze_material(
    company_id: str,
    company_name: str,
    ticker: str,
    document_id: str,
) -> dict:
    """
    Analyze an investor material by its ID in the investor_materials table.
    Fetches raw_content, runs the analysis agent, and stores the result.
    """
    from src.agents.summary_agent import analyze_investor_material

    client = get_supabase_client()

    result = (
        client.table("investor_materials_ML_REIT")
        .select("*")
        .eq("id", document_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise ValueError(f"Investor material {document_id} not found")

    material = result.data[0]

    if not material.get("raw_content"):
        raise ValueError(f"Investor material {document_id} has no raw_content")

    analysis, metadata = await analyze_investor_material(
        company_name=company_name,
        ticker=ticker,
        material_content=material["raw_content"],
        material_type=material.get("material_type", "investor material"),
    )

    from datetime import datetime

    client.table("investor_materials_ML_REIT").update({
        "analysis_json": analysis.model_dump(),
        "analyzed_at": datetime.utcnow().isoformat(),
    }).eq("id", document_id).execute()

    logger.info("Investor material analysis stored for %s (doc: %s)", ticker, document_id)
    return analysis.model_dump()
