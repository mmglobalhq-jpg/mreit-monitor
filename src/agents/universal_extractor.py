"""
Universal extractor — sends any document to an AI model and returns a UniversalExtraction.

Works for all 7 companies and all document types. Selects the correct prompt
based on document_type and injects company context. Supports Claude, OpenAI,
and Gemini models via the model_router.
"""

import json
import logging

from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.company_registry import CompanyConfig
from src.config.settings import settings
from src.models.universal_schemas import UniversalExtraction

logger = logging.getLogger("mreit-monitor.universal_extractor")

_docling_converter = None


def _get_docling_converter():
    """Return a module-level DocumentConverter, loading models once per process."""
    global _docling_converter
    if _docling_converter is None:
        from docling.document_converter import DocumentConverter
        _docling_converter = DocumentConverter()
        logger.info("docling DocumentConverter initialized")
    return _docling_converter


def _extract_pdf_text(content: bytes) -> str:
    """Extract text from PDF bytes. Tries docling first, falls back to pdfplumber."""
    import io

    # Try docling — richer markdown with tables preserved
    try:
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            converter = _get_docling_converter()
            result = converter.convert(tmp_path)
            text = result.document.export_to_markdown()
        finally:
            os.unlink(tmp_path)

        if text.strip():
            logger.debug("docling extracted %d chars from PDF", len(text))
            return text
        logger.warning("docling returned empty text — falling back to pdfplumber")
    except Exception as e:
        logger.warning("docling PDF extraction failed (%s) — falling back to pdfplumber", e)

    # Fallback: pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        text = "\n\n".join(p for p in pages if p.strip())
        if text.strip():
            return text
        return "[PDF contained no extractable text]"
    except Exception as e:
        logger.warning("pdfplumber fallback also failed (%s)", e)
        return content.decode("utf-8", errors="replace")


def _build_extraction_request(
    content: str | bytes,
    document_type: str,
    company_config: CompanyConfig,
    is_pdf: bool = False,
) -> tuple[str, str | list]:
    """Build system prompt and user content for extraction. Provider-agnostic."""
    from src.agents.prompts.extraction_prompts import get_extraction_prompts, _PREAMBLE

    schema_json = json.dumps(UniversalExtraction.model_json_schema(), indent=2)
    system_template, user_template = get_extraction_prompts(document_type)

    preamble = _PREAMBLE.format(
        document_type=document_type,
        company_name=company_config.name,
        ticker=[t for t, c in _registry_items() if c is company_config][0] if company_config else "UNKNOWN",
        primary_focus=", ".join(company_config.primary_focus),
        notes=company_config.notes,
    )

    system_prompt = system_template.format(preamble=preamble)

    if is_pdf and isinstance(content, bytes):
        # Extract text from PDF using docling (best quality) with pdfplumber fallback
        text_content = _extract_pdf_text(content)
        if len(text_content) > 200_000:
            text_content = text_content[:200_000] + "\n\n[TRUNCATED]"
        user_content = user_template.format(
            company_name=company_config.name,
            ticker=_ticker_for(company_config),
            primary_focus=", ".join(company_config.primary_focus),
            content=text_content,
            schema_json=schema_json,
        )
    else:
        text_content = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
        if len(text_content) > 200_000:
            text_content = text_content[:200_000] + "\n\n[TRUNCATED — document exceeds 200k chars]"

        user_content = user_template.format(
            company_name=company_config.name,
            ticker=_ticker_for(company_config),
            primary_focus=", ".join(company_config.primary_focus),
            content=text_content,
            schema_json=schema_json,
        )

    return system_prompt, user_content


def _parse_extraction_response(response_text: str, defaults: dict | None = None) -> UniversalExtraction:
    """Parse raw model response text into a UniversalExtraction.

    Args:
        response_text: Raw JSON string from the model
        defaults: Optional dict of fallback values for required fields that
                  models may leave null (source_url, document_date, etc.)
    """
    response_text = response_text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

    data = json.loads(response_text)

    # Patch required fields that non-Claude models often leave null
    if defaults:
        for key, val in defaults.items():
            if data.get(key) is None:
                data[key] = val
    # Ensure required fields have sane defaults even without explicit defaults
    if data.get("source_url") is None:
        data["source_url"] = ""
    if data.get("document_date") is None:
        from datetime import date as _d
        data["document_date"] = _d.today().isoformat()
    if data.get("additional_data") is None:
        data["additional_data"] = {}

    return UniversalExtraction.model_validate(data)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    reraise=True,
)
async def extract_document(
    content: str | bytes,
    document_type: str,
    company_config: CompanyConfig,
    source_url: str = "",
    is_pdf: bool = False,
    model_override: str | None = None,
) -> tuple[UniversalExtraction, dict]:
    """
    Extract structured data from any document into UniversalExtraction.

    Args:
        content: Document text (str) or PDF bytes
        document_type: e.g. 'quarterly_earnings', 'financial_supplement'
        company_config: CompanyConfig for the company
        source_url: URL the document came from
        is_pdf: True if content is PDF bytes
        model_override: Use a specific model instead of settings.extraction_model

    Returns:
        Tuple of (UniversalExtraction model, metadata dict)
    """
    from src.agents.model_router import extract_with_model

    model = model_override or settings.extraction_model
    system_prompt, user_content = _build_extraction_request(
        content, document_type, company_config, is_pdf
    )

    logger.info(
        "Extracting %s for %s via %s...",
        document_type, company_config.name, model,
    )

    response_text, metadata = await extract_with_model(
        model=model,
        system_prompt=system_prompt,
        user_content=user_content,
        max_tokens=32768,
    )

    try:
        extraction = _parse_extraction_response(response_text)
    except (json.JSONDecodeError, Exception) as e:
        logger.error("Failed to parse universal extraction: %s", str(e)[:200])
        logger.debug("Raw response: %s", response_text[:500])
        raise

    logger.info(
        "Extracted %s for %s: confidence=%.2f, fields=%d",
        document_type,
        company_config.name,
        extraction.extraction_confidence,
        len(extraction.fields_extracted),
    )

    metadata["raw_response"] = response_text

    return extraction, metadata


async def store_universal_extraction(
    extraction: UniversalExtraction,
    document_id: str,
    company_id: str,
) -> dict:
    """Write a UniversalExtraction to the universal_extractions table."""
    from src.services.supabase_client import get_supabase_client

    client = get_supabase_client()

    row = {
        "company_id": company_id,
        "document_id": document_id,
        "document_type": extraction.document_type,
        "period_end": extraction.period_end.isoformat(),
        "fiscal_quarter": extraction.fiscal_quarter,
        "fiscal_year": extraction.fiscal_year,
        # Indexed columns
        "book_value_per_share": extraction.book_value_per_share,
        "earnings_per_share": extraction.earnings_per_share,
        "dividends_per_share": extraction.dividends_per_share,
        "economic_return_pct": extraction.economic_return_pct,
        "net_interest_spread": extraction.net_interest_spread,
        "leverage_ratio": extraction.leverage_ratio,
        "portfolio_size": extraction.portfolio_size,
        "agency_rmbs_holdings": extraction.agency_rmbs_holdings,
        "weighted_avg_coupon": extraction.weighted_avg_coupon,
        "avg_asset_yield": extraction.avg_asset_yield,
        "avg_cost_of_funds": extraction.avg_cost_of_funds,
        # Flexible columns
        "extraction_data": extraction.model_dump(mode="json"),
        "management_commentary": extraction.management_commentary,
        "key_highlights": extraction.key_highlights,
        "extraction_confidence": extraction.extraction_confidence,
    }

    existing = (
        client.table("reit_universal_extractions")
        .select("id")
        .eq("document_id", document_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        result = (
            client.table("reit_universal_extractions")
            .update(row)
            .eq("document_id", document_id)
            .execute()
        )
    else:
        result = (
            client.table("reit_universal_extractions")
            .insert(row)
            .execute()
        )

    logger.info(
        "Stored universal extraction for document %s (company %s)",
        document_id, company_id,
    )

    return result.data[0] if result.data else row


def _registry_items():
    """Lazy import to avoid circular imports."""
    from src.config.company_registry import COMPANY_REGISTRY
    return COMPANY_REGISTRY.items()


def _ticker_for(config: CompanyConfig) -> str:
    """Look up ticker for a CompanyConfig."""
    for ticker, c in _registry_items():
        if c is config:
            return ticker
    return "UNKNOWN"
