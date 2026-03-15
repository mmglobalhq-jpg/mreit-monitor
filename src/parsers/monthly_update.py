"""
Monthly update parser — orchestrates the full processing pipeline
for a single monthly company update PDF.

Pipeline:
1. Download PDF
2. Upload to Supabase Storage
3. Send to Claude for structured extraction
4. Validate and store extracted data in Supabase
5. Run comparison agent against prior month
6. Send email alert
7. Update filing status
"""

import json
import logging
import re
from datetime import date, datetime

from dateutil import parser as dateutil_parser

from src.models.schemas import FilingStatus, FilingType, MonthlyUpdateExtraction
from src.parsers.utils import get_nested as _get_nested, parse_date_string as _parse_date_string
from src.services.supabase_client import get_supabase_client

logger = logging.getLogger("mreit-monitor.monthly_parser")


async def process_monthly_update(
    company_id: str,
    company_name: str,
    ticker: str,
    source_url: str,
    filing_date: date,
    period_label: str,
) -> bool:
    """
    Full pipeline for processing a single monthly update PDF.
    
    Returns True if processing completed successfully.
    """
    from src.services.downloader import download_pdf, upload_to_storage, build_storage_path
    from src.agents.extraction_agent import extract_monthly_update
    from src.agents.comparison_agent import generate_monthly_comparison
    from src.services.email_service import send_filing_alert
    
    client = get_supabase_client()
    filing_id = None
    
    try:
        # ============================================================
        # Step 1: Create filing record
        # ============================================================
        filing_record = {
            "company_id": company_id,
            "filing_type": FilingType.MONTHLY_UPDATE.value,
            "status": FilingStatus.DETECTED.value,
            "source_url": source_url,
            "source_page": "monthly_company_updates",
            "filing_date": filing_date.isoformat(),
            "period_label": period_label,
        }
        result = client.table("filings").insert(filing_record).execute()
        filing_id = result.data[0]["id"]
        logger.info("Created filing record %s for %s %s", filing_id, ticker, period_label)
        
        # ============================================================
        # Step 2: Download PDF
        # ============================================================
        pdf_bytes = await download_pdf(source_url)
        
        # ============================================================
        # Step 3: Upload to Supabase Storage
        # ============================================================
        storage_path = build_storage_path(ticker, "monthly_update", period_label)
        await upload_to_storage(pdf_bytes, storage_path)
        
        client.table("filings").update({
            "status": FilingStatus.DOWNLOADED.value,
            "storage_path": storage_path,
            "downloaded_at": datetime.utcnow().isoformat(),
        }).eq("id", filing_id).execute()
        
        # ============================================================
        # Step 4: Extract structured data via Claude
        # ============================================================
        client.table("filings").update({
            "status": FilingStatus.EXTRACTING.value,
        }).eq("id", filing_id).execute()
        
        # Get prior month's footnotes for change detection
        prior_footnotes = _get_prior_footnotes(client, company_id)
        
        extraction, extraction_meta = await extract_monthly_update(pdf_bytes, prior_footnotes)
        
        client.table("filings").update({
            "status": FilingStatus.EXTRACTED.value,
            "extraction_model": extraction_meta["model"],
            "extraction_tokens_used": extraction_meta["input_tokens"] + extraction_meta["output_tokens"],
            "raw_extraction_json": json.loads(extraction_meta["raw_response"]),
            "extracted_at": datetime.utcnow().isoformat(),
        }).eq("id", filing_id).execute()
        
        # ============================================================
        # Step 5: Store structured data in Supabase tables
        # ============================================================
        await _store_monthly_data(client, filing_id, company_id, extraction)
        
        logger.info("Stored structured data for %s %s", ticker, period_label)
        
        # ============================================================
        # Step 6: Run comparison agent
        # ============================================================
        client.table("filings").update({
            "status": FilingStatus.COMPARING.value,
        }).eq("id", filing_id).execute()
        
        prior_data = _get_prior_monthly_data(client, company_id, extraction.data_as_of_date)
        
        analysis = None
        if prior_data:
            current_data = extraction.model_dump()
            analysis, comparison_meta = await generate_monthly_comparison(
                company_name=company_name,
                ticker=ticker,
                current_period=period_label,
                prior_period=prior_data["period_label"],
                current_data=current_data,
                prior_data=prior_data["data"],
            )
            
            # Store analysis
            client.table("agent_analyses").insert({
                "filing_id": filing_id,
                "company_id": company_id,
                "analysis_type": "monthly_comparison",
                "period_label": f"{period_label} vs {prior_data['period_label']}",
                "summary": analysis.summary,
                "full_analysis": analysis.full_analysis,
                "key_changes": [c.model_dump() for c in analysis.key_metric_changes],
                "anomalies": [a.model_dump() for a in analysis.anomalies],
                "current_period_date": extraction.data_as_of_date,
                "prior_period_date": prior_data["as_of_date"],
                "model_used": comparison_meta["model"],
                "tokens_used": comparison_meta["input_tokens"] + comparison_meta["output_tokens"],
            }).execute()
            
            logger.info("Comparison analysis stored for %s %s", ticker, period_label)
        else:
            logger.info("No prior month data for comparison — skipping comparison agent")
        
        # ============================================================
        # Step 7: Send email alert
        # ============================================================
        metrics_summary = _build_metrics_summary(extraction, prior_data)
        
        await send_filing_alert(
            ticker=ticker,
            company_name=company_name,
            filing_type_label="Monthly Update",
            period_label=period_label,
            source_url=source_url,
            analysis=analysis,
            metrics_summary=metrics_summary,
        )
        
        # ============================================================
        # Step 8: Mark complete
        # ============================================================
        client.table("filings").update({
            "status": FilingStatus.COMPLETED.value,
            "completed_at": datetime.utcnow().isoformat(),
        }).eq("id", filing_id).execute()
        
        logger.info("Successfully processed %s %s monthly update", ticker, period_label)
        return True
        
    except Exception as e:
        logger.error("Failed to process %s %s: %s", ticker, period_label, str(e))
        if filing_id:
            client.table("filings").update({
                "status": FilingStatus.EXTRACTION_FAILED.value,
                "error_message": str(e)[:1000],
            }).eq("id", filing_id).execute()
        raise


async def _store_monthly_data(
    client,
    filing_id: str,
    company_id: str,
    extraction: MonthlyUpdateExtraction,
) -> None:
    """Store all extracted monthly data into the appropriate Supabase tables."""

    as_of_date = extraction.data_as_of_date

    # Monthly metrics (headline numbers)
    metrics = {
        "filing_id": filing_id,
        "company_id": company_id,
        "as_of_date": as_of_date,
        "stock_price": extraction.key_metrics.stock_price,
        "debt_equity": extraction.key_metrics.debt_equity,
        "implied_leverage": extraction.key_metrics.implied_leverage,
        "liquidity_millions": extraction.key_metrics.liquidity_millions,
        "liquidity_pct_capital": extraction.key_metrics.liquidity_pct_capital,
        "market_cap_millions": extraction.key_metrics.market_cap_millions,
        "monthly_dividend": extraction.dividend_info.monthly_dividend,
        "dividend_yield": extraction.dividend_info.dividend_yield,
    }

    # Parse and store dividend dates (GAP-10)
    if extraction.dividend_info.ex_dividend_date:
        metrics["ex_dividend_date"] = _parse_date_string(extraction.dividend_info.ex_dividend_date)
    if extraction.dividend_info.record_date:
        metrics["record_date"] = _parse_date_string(extraction.dividend_info.record_date)
    if extraction.dividend_info.pay_date:
        metrics["pay_date"] = _parse_date_string(extraction.dividend_info.pay_date)

    # Add portfolio totals from subtotal rows (GAP-2)
    for pos in extraction.portfolio_positions:
        st_lower = pos.security_type.lower()
        if pos.security_type == "Total Portfolio" or (pos.is_subtotal and "total portfolio" in st_lower):
            metrics["total_portfolio_value_millions"] = pos.market_value_millions
        elif pos.security_type == "Agency Portfolio" or (pos.is_subtotal and "agency" in st_lower and "portfolio" in st_lower):
            metrics["agency_portfolio_pct"] = pos.pct_portfolio
            metrics["agency_portfolio_value_millions"] = pos.market_value_millions
        elif "tba" in st_lower or "net tba" in st_lower:
            metrics["tba_positions_pct"] = pos.pct_portfolio
            metrics["tba_positions_value_millions"] = pos.market_value_millions
        elif "treasury" in st_lower and ("long" in st_lower or "position" in st_lower):
            metrics["treasury_positions_pct"] = pos.pct_portfolio
            metrics["treasury_positions_value_millions"] = pos.market_value_millions

    # Add repo totals (GAP-2) — column names match DB: total_repo_*, buckler_*
    for repo in extraction.repo_positions:
        if repo.is_total:
            metrics["total_repo_borrowed_millions"] = repo.principal_borrowed_millions
            metrics["total_repo_wtd_avg_original_term_days"] = repo.wtd_avg_original_term_days
            metrics["total_repo_wtd_avg_remaining_term_days"] = repo.wtd_avg_remaining_term_days
        elif repo.is_affiliate:
            metrics["buckler_repo_millions"] = repo.principal_borrowed_millions
            metrics["buckler_repo_pct"] = repo.pct_of_repo

    # Add swap totals (GAP-2) — column names match DB: total_swap_*
    for swap in extraction.swap_positions:
        if swap.is_total:
            metrics["total_swap_notional_millions"] = swap.notional_millions
            metrics["total_swap_wtd_avg_term_months"] = swap.wtd_avg_remaining_term_months
            metrics["total_swap_wtd_avg_rate"] = swap.wtd_avg_rate

    # Add hedge summary (GAP-2) — column names match DB: swap_hedge_*, treasury_futures_*
    for hedge in extraction.hedge_summary:
        ht_lower = hedge.hedge_type.lower()
        if "swap" in ht_lower:
            metrics["swap_hedge_notional_millions"] = hedge.notional_millions
        elif "treasury" in ht_lower or "futures" in ht_lower:
            metrics["treasury_futures_notional_millions"] = hedge.notional_millions

    # Upsert monthly metrics (unique on company_id + as_of_date)
    client.table("monthly_metrics").upsert(metrics, on_conflict="company_id,as_of_date").execute()

    # Portfolio positions
    for pos in extraction.portfolio_positions:
        client.table("portfolio_positions").insert({
            "filing_id": filing_id,
            "company_id": company_id,
            "as_of_date": as_of_date,
            "security_type": pos.security_type,
            "coupon": pos.coupon,
            "is_subtotal": pos.is_subtotal,
            "parent_category": pos.parent_category,
            "pct_portfolio": pos.pct_portfolio,
            "market_value_millions": pos.market_value_millions,
            "effective_duration": pos.effective_duration,
        }).execute()

    # Repo positions
    for repo in extraction.repo_positions:
        client.table("repo_positions").insert({
            "filing_id": filing_id,
            "company_id": company_id,
            "as_of_date": as_of_date,
            "counterparty": repo.counterparty,
            "is_affiliate": repo.is_affiliate,
            "is_total": repo.is_total,
            "principal_borrowed_millions": repo.principal_borrowed_millions,
            "pct_of_repo": repo.pct_of_repo,
            "wtd_avg_original_term_days": repo.wtd_avg_original_term_days,
            "wtd_avg_remaining_term_days": repo.wtd_avg_remaining_term_days,
            "longest_maturity_days": repo.longest_maturity_days,
        }).execute()

    # Swap positions
    for swap in extraction.swap_positions:
        client.table("swap_positions").insert({
            "filing_id": filing_id,
            "company_id": company_id,
            "as_of_date": as_of_date,
            "maturity_bucket": swap.maturity_bucket,
            "is_total": swap.is_total,
            "notional_millions": swap.notional_millions,
            "wtd_avg_remaining_term_months": swap.wtd_avg_remaining_term_months,
            "wtd_avg_rate": swap.wtd_avg_rate,
        }).execute()

    # CPR data (GAP-1)
    if extraction.cpr_data:
        for cpr in extraction.cpr_data:
            cpr_date = _parse_cpr_month(cpr.month)
            if cpr_date and cpr.cpr_value is not None:
                client.table("cpr_data").upsert({
                    "company_id": company_id,
                    "filing_id": filing_id,
                    "month": cpr_date,
                    "cpr_value": cpr.cpr_value,
                }, on_conflict="company_id,month").execute()

    # Footnotes with change detection (GAP-4)
    prior_footnote_map = _build_prior_footnote_map(client, company_id, as_of_date)

    for fn in extraction.footnotes:
        changed = False
        prior_text = None

        if prior_footnote_map and fn.number in prior_footnote_map:
            prior_text_val = prior_footnote_map[fn.number]
            if prior_text_val != fn.text:
                changed = True
                prior_text = prior_text_val

        client.table("filing_footnotes").insert({
            "filing_id": filing_id,
            "company_id": company_id,
            "as_of_date": as_of_date,
            "footnote_number": fn.number,
            "footnote_text": fn.text,
            "changed_from_prior": changed,
            "prior_text": prior_text,
        }).execute()


def _get_prior_footnotes(client, company_id: str) -> list[dict] | None:
    """Get the most recent footnotes for a company (for Claude prompt context)."""
    # First find the most recent as_of_date that has footnotes
    latest = (
        client.table("filing_footnotes")
        .select("as_of_date")
        .eq("company_id", company_id)
        .order("as_of_date", desc=True)
        .limit(1)
        .execute()
    )
    if not latest.data:
        return None

    latest_date = latest.data[0]["as_of_date"]

    # Then get all footnotes from that date
    result = (
        client.table("filing_footnotes")
        .select("footnote_number, footnote_text")
        .eq("company_id", company_id)
        .eq("as_of_date", latest_date)
        .order("footnote_number")
        .execute()
    )
    return result.data if result.data else None


def _build_prior_footnote_map(client, company_id: str, current_as_of: str) -> dict[int, str] | None:
    """Build a {number: text} map from the most recent footnotes before current_as_of."""
    latest = (
        client.table("filing_footnotes")
        .select("as_of_date")
        .eq("company_id", company_id)
        .lt("as_of_date", current_as_of)
        .order("as_of_date", desc=True)
        .limit(1)
        .execute()
    )
    if not latest.data:
        return None

    prior_date = latest.data[0]["as_of_date"]
    result = (
        client.table("filing_footnotes")
        .select("footnote_number, footnote_text")
        .eq("company_id", company_id)
        .eq("as_of_date", prior_date)
        .execute()
    )
    if not result.data:
        return None
    return {r["footnote_number"]: r["footnote_text"] for r in result.data}


def _get_prior_monthly_data(client, company_id: str, current_as_of: str) -> dict | None:
    """Get the prior month's complete data for comparison."""
    # Get the most recent monthly metrics before current_as_of
    result = (
        client.table("monthly_metrics")
        .select("*")
        .eq("company_id", company_id)
        .lt("as_of_date", current_as_of)
        .order("as_of_date", desc=True)
        .limit(1)
        .execute()
    )
    
    if not result.data:
        return None
    
    prior_metrics = result.data[0]
    prior_filing_id = prior_metrics["filing_id"]
    prior_as_of = prior_metrics["as_of_date"]
    
    # Get the prior period's raw extraction JSON from the filings table
    filing_result = (
        client.table("filings")
        .select("raw_extraction_json, period_label")
        .eq("id", prior_filing_id)
        .limit(1)
        .execute()
    )
    
    if not filing_result.data or not filing_result.data[0].get("raw_extraction_json"):
        return None
    
    return {
        "as_of_date": prior_as_of,
        "period_label": filing_result.data[0]["period_label"],
        "data": filing_result.data[0]["raw_extraction_json"],
    }


def _build_metrics_summary(
    extraction: MonthlyUpdateExtraction,
    prior_data: dict | None,
) -> list[dict]:
    """Build a summary of key metrics with deltas for the email alert."""
    # (name, current_value, suffix, dotted_path into prior_data["data"])
    metrics = [
        ("Stock Price", extraction.key_metrics.stock_price, "$", "key_metrics.stock_price"),
        ("Debt/Equity", extraction.key_metrics.debt_equity, "x", "key_metrics.debt_equity"),
        ("Implied Leverage", extraction.key_metrics.implied_leverage, "x", "key_metrics.implied_leverage"),
        ("Liquidity ($M)", extraction.key_metrics.liquidity_millions, "", "key_metrics.liquidity_millions"),
        ("Liquidity % Capital", extraction.key_metrics.liquidity_pct_capital, "%", "key_metrics.liquidity_pct_capital"),
        ("Monthly Dividend", extraction.dividend_info.monthly_dividend, "$", "dividend_info.monthly_dividend"),
        ("Dividend Yield", extraction.dividend_info.dividend_yield, "%", "dividend_info.dividend_yield"),
    ]

    prior = prior_data["data"] if prior_data else None

    summary = []
    for name, current_val, suffix, path in metrics:
        entry = {"name": name}

        # Format current value
        if current_val is not None:
            entry["current"] = f"{'$' if suffix == '$' else ''}{current_val}{suffix if suffix != '$' else ''}"
        else:
            entry["current"] = "—"

        # Look up prior value
        prior_val = _get_nested(prior, path) if prior else None

        if prior_val is not None:
            entry["prior"] = f"{'$' if suffix == '$' else ''}{prior_val}{suffix if suffix != '$' else ''}"

            if current_val is not None:
                delta = current_val - prior_val
                if suffix == "$":
                    entry["delta_str"] = f"{'+' if delta >= 0 else ''}${delta:.2f}"
                elif suffix == "x":
                    entry["delta_str"] = f"{'+' if delta >= 0 else ''}{delta:.1f}x"
                elif suffix == "%":
                    entry["delta_str"] = f"{'+' if delta >= 0 else ''}{delta:.1f}pp"
                else:
                    entry["delta_str"] = f"{'+' if delta >= 0 else ''}{delta:.1f}"

                if abs(delta) < 0.001:
                    entry["direction"] = "flat"
                elif delta > 0:
                    entry["direction"] = "up"
                else:
                    entry["direction"] = "down"
            else:
                entry["delta_str"] = "—"
                entry["direction"] = "flat"
        else:
            entry["prior"] = "—"
            entry["delta_str"] = "—"
            entry["direction"] = "flat"

        summary.append(entry)

    return summary


# Month abbreviation map for CPR labels like "J 2024", "F 2025", "Mr 2025"
_CPR_MONTH_MAP = {
    "j": 1, "f": 2, "mr": 3, "a": 4, "m": 5, "jn": 6,
    "jl": 7, "au": 8, "s": 9, "o": 10, "n": 11, "d": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4,
    "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}


def _parse_cpr_month(month_label: str) -> str | None:
    """Parse CPR chart month labels like 'J 2024', 'F 2025', 'Mr 2025' to '2024-01-01'."""
    if not month_label:
        return None
    parts = month_label.strip().split()
    if len(parts) != 2:
        # Try dateutil as fallback
        try:
            parsed = dateutil_parser.parse(month_label, fuzzy=True)
            return parsed.replace(day=1).date().isoformat()
        except (ValueError, TypeError):
            return None

    abbrev = parts[0].lower().rstrip(".")
    year_str = parts[1]

    month_num = _CPR_MONTH_MAP.get(abbrev)
    if month_num is None:
        return None

    try:
        year = int(year_str)
        return date(year, month_num, 1).isoformat()
    except (ValueError, TypeError):
        return None
