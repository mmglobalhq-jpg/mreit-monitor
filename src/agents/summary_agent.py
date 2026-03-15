"""
Summary agent — generates consolidated periodic reports and investor material analysis.

Consumes extracted data from Supabase and produces structured summary reports
on monthly/quarterly/annual cadences.
"""

import json
import logging

import anthropic
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import settings
from src.models.summary_schemas import SummaryReport, InvestorMaterialAnalysis

logger = logging.getLogger("mreit-monitor.summary_agent")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    reraise=True,
)
async def generate_summary_report(
    company_name: str,
    ticker: str,
    period_label: str,
    report_type: str,
    data_context: dict,
) -> tuple[SummaryReport, dict]:
    """
    Generate a consolidated summary report for a period.

    Args:
        company_name: Full company name
        ticker: Stock ticker
        period_label: e.g., "March 2026", "Q4 2025", "FY 2025"
        report_type: "monthly", "quarterly", or "annual"
        data_context: Dict with keys: monthly_data, quarterly_data, analyses,
                      portfolio_data, cpr_data

    Returns:
        Tuple of (SummaryReport model, metadata dict)
    """
    from src.agents.prompts.summary_templates import (
        SUMMARY_REPORT_SYSTEM,
        SUMMARY_REPORT_USER,
    )

    client = anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key,
        timeout=httpx.Timeout(timeout=600.0, connect=5.0),
    )
    schema_json = json.dumps(SummaryReport.model_json_schema(), indent=2)

    user_message = SUMMARY_REPORT_USER.format(
        company_name=company_name,
        ticker=ticker,
        period_label=period_label,
        report_type=report_type,
        monthly_data_json=json.dumps(data_context.get("monthly_data", []), indent=2, default=str),
        quarterly_data_json=json.dumps(data_context.get("quarterly_data", []), indent=2, default=str),
        analyses_json=json.dumps(data_context.get("analyses", []), indent=2, default=str),
        portfolio_data_json=json.dumps(data_context.get("portfolio_data", []), indent=2, default=str),
        cpr_data_json=json.dumps(data_context.get("cpr_data", []), indent=2, default=str),
        prior_monthly_metrics_json=json.dumps(data_context.get("prior_monthly_metrics", []), indent=2, default=str),
        prior_portfolio_positions_json=json.dumps(data_context.get("prior_portfolio_positions", {}), indent=2, default=str),
        prior_quarterly_metrics_json=json.dumps(data_context.get("prior_quarterly_metrics", []), indent=2, default=str),
        universal_extractions_json=json.dumps(data_context.get("universal_extractions", []), indent=2, default=str),
        prior_universal_extractions_json=json.dumps(data_context.get("prior_universal_extractions", []), indent=2, default=str),
        schema_json=schema_json,
    )

    logger.info(
        "Generating %s summary report for %s: %s",
        report_type, ticker, period_label,
    )

    response_text = ""
    async with client.messages.stream(
        model=settings.summary_model,
        max_tokens=12288,
        system=SUMMARY_REPORT_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        async for text in stream.text_stream:
            response_text += text
        message = await stream.get_final_message()

    response_text = response_text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

    try:
        data = json.loads(response_text)
        report = SummaryReport.model_validate(data)
    except (json.JSONDecodeError, Exception) as e:
        logger.error("Failed to parse summary report: %s", str(e)[:200])
        raise

    logger.info(
        "Summary report generated for %s %s. Sections with data: %d/6",
        ticker,
        period_label,
        sum(1 for s in [
            report.overall_summary,
            report.securities_detail,
            report.filing_highlights,
            report.performance_activity,
            report.supplemental_materials,
            report.data_gaps,
        ] if s.data_available),
    )

    metadata = {
        "model": settings.summary_model,
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
        "raw_response": response_text,
    }

    return report, metadata


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    reraise=True,
)
async def analyze_investor_material(
    company_name: str,
    ticker: str,
    material_content: str,
    material_type: str,
) -> tuple[InvestorMaterialAnalysis, dict]:
    """
    Analyze an ad-hoc investor material (presentation, transcript, etc.).

    Returns:
        Tuple of (InvestorMaterialAnalysis model, metadata dict)
    """
    from src.agents.prompts.summary_templates import (
        INVESTOR_MATERIAL_SYSTEM,
        INVESTOR_MATERIAL_USER,
    )

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    schema_json = json.dumps(InvestorMaterialAnalysis.model_json_schema(), indent=2)

    user_message = INVESTOR_MATERIAL_USER.format(
        company_name=company_name,
        ticker=ticker,
        material_type=material_type,
        material_content=material_content,
        schema_json=schema_json,
    )

    logger.info("Analyzing %s for %s", material_type, ticker)

    message = await client.messages.create(
        model=settings.summary_model,
        max_tokens=4096,
        system=INVESTOR_MATERIAL_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
    )

    response_text = ""
    for block in message.content:
        if block.type == "text":
            response_text += block.text

    response_text = response_text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

    try:
        data = json.loads(response_text)
        analysis = InvestorMaterialAnalysis.model_validate(data)
    except (json.JSONDecodeError, Exception) as e:
        logger.error("Failed to parse investor material analysis: %s", str(e)[:200])
        raise

    metadata = {
        "model": settings.summary_model,
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
        "raw_response": response_text,
    }

    return analysis, metadata
