"""
Extraction agent — sends PDFs and documents to Claude API for structured data extraction.

Handles:
- Monthly update PDFs → full PDF sent as base64 to Claude
- Quarterly earnings releases → HTML text sent to Claude  
- 10-Q/10-K sections → targeted text sections sent to Claude

All extraction calls return validated Pydantic models.
"""

import base64
import json
import logging

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import settings
from src.models.schemas import MonthlyUpdateExtraction, QuarterlyEarningsExtraction

logger = logging.getLogger("mreit-monitor.extraction_agent")


def _get_client() -> anthropic.AsyncAnthropic:
    """Get the Anthropic async client."""
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    reraise=True,
)
async def extract_monthly_update(
    pdf_bytes: bytes,
    prior_footnotes: list[dict] | None = None,
) -> tuple[MonthlyUpdateExtraction, dict]:
    """
    Extract structured data from a monthly company update PDF.
    
    Sends the full PDF to Claude API as base64 with the extraction prompt.
    Validates the response against the MonthlyUpdateExtraction schema.
    
    Args:
        pdf_bytes: Raw PDF file bytes
        prior_footnotes: Previous month's footnotes for change detection (optional)
        
    Returns:
        Validated MonthlyUpdateExtraction model
    """
    from src.agents.prompts.templates import MONTHLY_EXTRACTION_SYSTEM, MONTHLY_EXTRACTION_USER
    
    client = _get_client()
    
    # Build the schema JSON for the prompt
    schema_json = json.dumps(MonthlyUpdateExtraction.model_json_schema(), indent=2)
    
    # Build user message with PDF
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    
    user_content = [
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": pdf_b64,
            },
        },
        {
            "type": "text",
            "text": MONTHLY_EXTRACTION_USER.format(schema_json=schema_json),
        },
    ]
    
    # Add prior footnotes context if available
    system_prompt = MONTHLY_EXTRACTION_SYSTEM
    if prior_footnotes:
        system_prompt += f"\n\nPrior month's footnotes for change detection:\n{json.dumps(prior_footnotes, indent=2)}"
    
    logger.info("Sending monthly PDF to Claude %s for extraction...", settings.extraction_model)
    
    message = await client.messages.create(
        model=settings.extraction_model,
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    
    # Extract the text response
    response_text = ""
    for block in message.content:
        if block.type == "text":
            response_text += block.text
    
    # Clean up any markdown formatting Claude might add
    response_text = response_text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1]  # Remove first line
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
    
    # Parse and validate
    try:
        data = json.loads(response_text)
        extraction = MonthlyUpdateExtraction.model_validate(data)
    except (json.JSONDecodeError, Exception) as e:
        logger.error("Failed to parse extraction response: %s", str(e)[:200])
        logger.debug("Raw response: %s", response_text[:500])
        raise
    
    logger.info(
        "Successfully extracted monthly update: %s (as of %s)",
        extraction.update_month,
        extraction.data_as_of_date,
    )
    
    return extraction, {
        "model": settings.extraction_model,
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
        "raw_response": response_text,
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    reraise=True,
)
async def extract_quarterly_earnings(
    content: str,
) -> tuple[QuarterlyEarningsExtraction, dict]:
    """
    Extract structured data from a quarterly earnings release (HTML/text).
    
    Args:
        content: The earnings release text content
        
    Returns:
        Validated QuarterlyEarningsExtraction model
    """
    from src.agents.prompts.templates import QUARTERLY_EXTRACTION_SYSTEM, QUARTERLY_EXTRACTION_USER
    
    client = _get_client()
    schema_json = json.dumps(QuarterlyEarningsExtraction.model_json_schema(), indent=2)
    
    logger.info("Sending earnings release to Claude %s for extraction...", settings.extraction_model)
    
    message = await client.messages.create(
        model=settings.extraction_model,
        max_tokens=4096,
        system=QUARTERLY_EXTRACTION_SYSTEM,
        messages=[{
            "role": "user",
            "content": QUARTERLY_EXTRACTION_USER.format(
                content=content,
                schema_json=schema_json,
            ),
        }],
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
        extraction = QuarterlyEarningsExtraction.model_validate(data)
    except (json.JSONDecodeError, Exception) as e:
        logger.error("Failed to parse quarterly extraction: %s", str(e)[:200])
        raise
    
    logger.info("Successfully extracted quarterly earnings: %s", extraction.quarter_label)
    
    return extraction, {
        "model": settings.extraction_model,
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
        "raw_response": response_text,
    }
