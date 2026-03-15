"""
Comparison agent — generates period-over-period delta analysis.

Takes current and prior period structured data, sends to Claude Opus,
and produces a detailed comparative analysis with anomaly detection.
"""

import json
import logging

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import settings
from src.models.schemas import ComparisonAnalysis

logger = logging.getLogger("mreit-monitor.comparison_agent")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    reraise=True,
)
async def generate_monthly_comparison(
    company_name: str,
    ticker: str,
    current_period: str,
    prior_period: str,
    current_data: dict,
    prior_data: dict,
) -> tuple[ComparisonAnalysis, dict]:
    """
    Generate a comparative analysis between two monthly periods.
    
    Args:
        company_name: Full company name
        ticker: Stock ticker
        current_period: Label for current period (e.g., "March 2026")
        prior_period: Label for prior period (e.g., "February 2026")
        current_data: Current period's extracted data as dict
        prior_data: Prior period's extracted data as dict
        
    Returns:
        Tuple of (ComparisonAnalysis model, metadata dict)
    """
    from src.agents.prompts.templates import COMPARISON_SYSTEM, COMPARISON_USER
    
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    schema_json = json.dumps(ComparisonAnalysis.model_json_schema(), indent=2)
    
    user_message = COMPARISON_USER.format(
        company_name=company_name,
        ticker=ticker,
        current_period=current_period,
        prior_period=prior_period,
        current_data_json=json.dumps(current_data, indent=2, default=str),
        prior_data_json=json.dumps(prior_data, indent=2, default=str),
        schema_json=schema_json,
    )
    
    logger.info(
        "Generating %s comparison for %s: %s vs %s",
        "monthly", ticker, current_period, prior_period,
    )
    
    message = await client.messages.create(
        model=settings.comparison_model,
        max_tokens=8192,
        system=COMPARISON_SYSTEM,
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
        analysis = ComparisonAnalysis.model_validate(data)
    except (json.JSONDecodeError, Exception) as e:
        logger.error("Failed to parse comparison analysis: %s", str(e)[:200])
        raise
    
    logger.info(
        "Comparison complete for %s. Anomalies found: %d",
        ticker, len(analysis.anomalies),
    )
    
    metadata = {
        "model": settings.comparison_model,
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
        "raw_response": response_text,
    }
    
    return analysis, metadata
