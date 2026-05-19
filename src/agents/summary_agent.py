"""
Summary agent — generates consolidated periodic reports and investor material analysis.

Consumes extracted data from Supabase and produces structured summary reports
on monthly/quarterly/annual cadences.
"""

import asyncio
import json
import logging

import httpx
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import settings
from src.models.summary_schemas import SummaryReport, InvestorMaterialAnalysis
from src.services.metering import record_llm_call

logger = logging.getLogger("mreit-monitor.summary_agent")

AGENT_VERSION = "2.1.0"  # verification pass + dollar MoM + anti-AI-writing


def _openrouter_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        default_headers={
            "HTTP-Referer": "https://hq.mmglobal.us",
            "X-Title": "Tom Bot mREIT Monitor",
        },
        timeout=httpx.Timeout(timeout=600.0, connect=10.0),
    )


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

    client = _openrouter_client()
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
        source_documents_json=json.dumps(data_context.get("source_documents", []), indent=2, default=str),
        schema_json=schema_json,
    )

    logger.info(
        "Generating %s summary report for %s: %s",
        report_type, ticker, period_label,
    )

    response_text = ""
    input_tokens = 0
    output_tokens = 0

    stream = await client.chat.completions.create(
        model=settings.summary_model,
        max_tokens=12288,
        messages=[
            {"role": "system", "content": SUMMARY_REPORT_SYSTEM},
            {"role": "user", "content": user_message},
        ],
        stream=True,
        stream_options={"include_usage": True},
    )
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            response_text += chunk.choices[0].delta.content
        if chunk.usage:
            input_tokens = chunk.usage.prompt_tokens
            output_tokens = chunk.usage.completion_tokens

    asyncio.create_task(record_llm_call(
        provider="openrouter",
        model=settings.summary_model,
        prompt_tokens=input_tokens,
        completion_tokens=output_tokens,
        feature="reit_summary",
    ))

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
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "raw_response": response_text,
    }

    report, metadata = await _verify_and_correct(
        report, metadata, data_context, client,
        company_name, ticker, period_label, report_type,
    )

    return report, metadata


async def _verify_and_correct(
    report: SummaryReport,
    metadata: dict,
    data_context: dict,
    client: AsyncOpenAI,
    company_name: str,
    ticker: str,
    period_label: str,
    report_type: str,
) -> tuple[SummaryReport, dict]:
    """
    Send the generated report + source data to the model for fact-checking.
    If errors are found, regenerate with corrections appended as guidance.
    """
    from src.agents.prompts.summary_templates import (
        VERIFICATION_SYSTEM,
        VERIFICATION_USER,
        SUMMARY_REPORT_SYSTEM,
        SUMMARY_REPORT_USER,
    )

    report_dict = report.model_dump()
    verification_msg = VERIFICATION_USER.format(
        report_json=json.dumps(report_dict, indent=2, default=str),
        portfolio_data_json=json.dumps(data_context.get("portfolio_data", []), indent=2, default=str),
        prior_portfolio_positions_json=json.dumps(data_context.get("prior_portfolio_positions", {}), indent=2, default=str),
        monthly_data_json=json.dumps(data_context.get("monthly_data", []), indent=2, default=str),
        prior_monthly_metrics_json=json.dumps(data_context.get("prior_monthly_metrics", []), indent=2, default=str),
    )

    logger.info("Running verification pass for %s %s", ticker, period_label)

    try:
        verify_response = await client.chat.completions.create(
            model=settings.summary_model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": VERIFICATION_SYSTEM},
                {"role": "user", "content": verification_msg},
            ],
        )

        verify_text = (verify_response.choices[0].message.content or "").strip()
        if verify_text.startswith("```"):
            verify_text = verify_text.split("\n", 1)[1]
            if verify_text.endswith("```"):
                verify_text = verify_text[:-3]
            verify_text = verify_text.strip()

        verification = json.loads(verify_text)
        errors = verification.get("errors", [])
        metadata["verification_tokens"] = {
            "input": verify_response.usage.prompt_tokens if verify_response.usage else 0,
            "output": verify_response.usage.completion_tokens if verify_response.usage else 0,
        }

        asyncio.create_task(record_llm_call(
            provider="openrouter",
            model=settings.summary_model,
            prompt_tokens=metadata["verification_tokens"]["input"],
            completion_tokens=metadata["verification_tokens"]["output"],
            feature="reit_summary_verify",
        ))

        if not errors:
            logger.info("Verification passed — no errors found")
            metadata["verified"] = True
            return report, metadata

        logger.warning("Verification found %d error(s), regenerating", len(errors))
        metadata["verification_errors"] = errors

        corrections_text = "\n".join(
            f"- CORRECTION: \"{e.get('claim', '')}\" is wrong. "
            f"Source says: {e.get('source_value', '')}. "
            f"Fix: {e.get('correction', '')}"
            for e in errors
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
        user_message += f"\n\nIMPORTANT — A prior draft had these errors. Fix them:\n{corrections_text}"

        regen_text = ""
        regen_input_tokens = 0
        regen_output_tokens = 0

        regen_stream = await client.chat.completions.create(
            model=settings.summary_model,
            max_tokens=12288,
            messages=[
                {"role": "system", "content": SUMMARY_REPORT_SYSTEM},
                {"role": "user", "content": user_message},
            ],
            stream=True,
            stream_options={"include_usage": True},
        )
        async for chunk in regen_stream:
            if chunk.choices and chunk.choices[0].delta.content:
                regen_text += chunk.choices[0].delta.content
            if chunk.usage:
                regen_input_tokens = chunk.usage.prompt_tokens
                regen_output_tokens = chunk.usage.completion_tokens

        asyncio.create_task(record_llm_call(
            provider="openrouter",
            model=settings.summary_model,
            prompt_tokens=regen_input_tokens,
            completion_tokens=regen_output_tokens,
            feature="reit_summary_regen",
        ))

        regen_text = regen_text.strip()
        if regen_text.startswith("```"):
            regen_text = regen_text.split("\n", 1)[1]
            if regen_text.endswith("```"):
                regen_text = regen_text[:-3]
            regen_text = regen_text.strip()

        regen_data = json.loads(regen_text)
        report = SummaryReport.model_validate(regen_data)

        metadata["regenerated"] = True
        metadata["regen_tokens"] = {
            "input": regen_input_tokens,
            "output": regen_output_tokens,
        }
        metadata["raw_response"] = regen_text
        logger.info("Regenerated report with %d corrections applied", len(errors))

    except Exception as e:
        logger.warning("Verification pass failed (non-fatal): %s", str(e)[:200])
        metadata["verified"] = False
        metadata["verification_error"] = str(e)[:200]

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

    client = _openrouter_client()
    schema_json = json.dumps(InvestorMaterialAnalysis.model_json_schema(), indent=2)

    user_message = INVESTOR_MATERIAL_USER.format(
        company_name=company_name,
        ticker=ticker,
        material_type=material_type,
        material_content=material_content,
        schema_json=schema_json,
    )

    logger.info("Analyzing %s for %s", material_type, ticker)

    response = await client.chat.completions.create(
        model=settings.summary_model,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": INVESTOR_MATERIAL_SYSTEM},
            {"role": "user", "content": user_message},
        ],
    )

    response_text = (response.choices[0].message.content or "").strip()
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
        "input_tokens": response.usage.prompt_tokens if response.usage else 0,
        "output_tokens": response.usage.completion_tokens if response.usage else 0,
        "raw_response": response_text,
    }

    asyncio.create_task(record_llm_call(
        provider="openrouter",
        model=settings.summary_model,
        prompt_tokens=metadata["input_tokens"],
        completion_tokens=metadata["output_tokens"],
        feature="reit_investor_material",
    ))

    return analysis, metadata
