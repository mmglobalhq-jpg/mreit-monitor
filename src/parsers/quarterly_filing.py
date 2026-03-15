"""
Quarterly filing parser — processes 10-Q and 10-K PDFs.

For these 100+ page documents, uses pdfplumber to extract key sections
(investment schedule, derivatives/hedging, MD&A), then sends each section
to Claude individually for structured extraction.

Pipeline:
1. Download PDF
2. Upload to Supabase Storage
3. Use pdfplumber to extract text and identify key sections
4. Send each section to Claude for structured extraction
5. Store results in Supabase (raw extraction as JSONB, MD&A in agent_analyses)
6. Mark filing complete
"""

import io
import json
import logging
import re
from datetime import date, datetime

import anthropic
import pdfplumber
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import settings
from src.models.schemas import FilingStatus, FilingType
from src.services.supabase_client import get_supabase_client

logger = logging.getLogger("mreit-monitor.quarterly_parser")

# Section header patterns used to identify key sections in 10-Q/10-K filings.
# Each entry maps a section key to a list of regex patterns (case-insensitive).
SECTION_PATTERNS: dict[str, list[str]] = {
    "investment_schedule": [
        r"schedule\s+of\s+investments",
        r"consolidated\s+schedule\s+of\s+investments",
        r"schedule\s+of\s+mortgage[\-\s]backed\s+securities",
    ],
    "derivatives": [
        r"derivative\s+financial\s+instruments",
        r"derivative\s+instruments",
        r"interest\s+rate\s+swap",
        r"hedging\s+activit",
        r"derivatives?\s+and\s+hedging",
    ],
    "mda": [
        r"management.s\s+discussion\s+and\s+analysis",
        r"management.s\s+discussion\s*&\s*analysis",
        r"md\s*&\s*a",
        r"item\s+2\.\s+management.s\s+discussion",
    ],
}

# Maximum number of pages to include in a single section sent to Claude.
# This keeps token usage reasonable and avoids hitting context limits.
MAX_SECTION_PAGES = 40


async def process_quarterly_filing(
    company_id: str,
    company_name: str,
    ticker: str,
    source_url: str,
    filing_date: date,
    period_label: str,  # e.g., "Q4 2025 10-K"
    filing_type: FilingType = FilingType.QUARTERLY_10Q,
) -> bool:
    """
    Full pipeline for processing a single 10-Q or 10-K filing PDF.

    Returns True if processing completed successfully.
    """
    from src.services.downloader import (
        build_storage_path,
        download_pdf,
        upload_to_storage,
    )

    client = get_supabase_client()
    filing_id = None

    try:
        # ==============================================================
        # Step 1: Create filing record
        # ==============================================================
        filing_record = {
            "company_id": company_id,
            "filing_type": filing_type.value,
            "status": FilingStatus.DETECTED.value,
            "source_url": source_url,
            "source_page": "quarterly_reports",
            "filing_date": filing_date.isoformat(),
            "period_label": period_label,
        }
        result = client.table("filings").insert(filing_record).execute()
        filing_id = result.data[0]["id"]
        logger.info(
            "Created filing record %s for %s %s", filing_id, ticker, period_label
        )

        # ==============================================================
        # Step 2: Download PDF
        # ==============================================================
        pdf_bytes = await download_pdf(source_url)

        # ==============================================================
        # Step 3: Upload to Supabase Storage
        # ==============================================================
        storage_path = build_storage_path(ticker, filing_type.value, period_label)
        await upload_to_storage(pdf_bytes, storage_path)

        client.table("filings").update(
            {
                "status": FilingStatus.DOWNLOADED.value,
                "storage_path": storage_path,
                "downloaded_at": datetime.utcnow().isoformat(),
            }
        ).eq("id", filing_id).execute()

        # ==============================================================
        # Step 4: Extract sections with pdfplumber
        # ==============================================================
        client.table("filings").update(
            {"status": FilingStatus.EXTRACTING.value}
        ).eq("id", filing_id).execute()

        sections = _extract_sections(pdf_bytes)

        if not sections:
            logger.warning(
                "No recognizable sections found in %s %s — storing raw text only",
                ticker,
                period_label,
            )

        logger.info(
            "Extracted %d sections from %s %s: %s",
            len(sections),
            ticker,
            period_label,
            list(sections.keys()),
        )

        # ==============================================================
        # Step 5: Send each section to Claude for extraction
        # ==============================================================
        from src.agents.prompts.templates import (
            DERIVATIVES_SECTION_SYSTEM,
            INVESTMENT_SCHEDULE_SYSTEM,
            MDA_ANALYSIS_SYSTEM,
        )

        extraction_results: dict[str, dict] = {}
        total_tokens = 0

        # Investment schedule
        if "investment_schedule" in sections:
            logger.info("Extracting investment schedule for %s %s", ticker, period_label)
            inv_result, inv_meta = await _extract_section_with_claude(
                sections["investment_schedule"],
                INVESTMENT_SCHEDULE_SYSTEM,
            )
            extraction_results["investment_schedule"] = inv_result
            total_tokens += inv_meta["input_tokens"] + inv_meta["output_tokens"]
            logger.info(
                "Investment schedule: extracted %d positions",
                len(inv_result) if isinstance(inv_result, list) else 0,
            )

        # Derivatives / hedging
        if "derivatives" in sections:
            logger.info("Extracting derivatives section for %s %s", ticker, period_label)
            deriv_result, deriv_meta = await _extract_section_with_claude(
                sections["derivatives"],
                DERIVATIVES_SECTION_SYSTEM,
            )
            extraction_results["derivatives"] = deriv_result
            total_tokens += deriv_meta["input_tokens"] + deriv_meta["output_tokens"]
            logger.info("Derivatives section extracted")

        # MD&A — returns a narrative summary, not structured JSON
        mda_summary = None
        if "mda" in sections:
            logger.info("Extracting MD&A section for %s %s", ticker, period_label)
            mda_result, mda_meta = await _extract_section_with_claude(
                sections["mda"],
                MDA_ANALYSIS_SYSTEM,
            )
            mda_summary = mda_result
            extraction_results["mda_summary"] = mda_result
            total_tokens += mda_meta["input_tokens"] + mda_meta["output_tokens"]
            logger.info("MD&A analysis complete")

        # ==============================================================
        # Step 6: Store results
        # ==============================================================

        # Store the full extraction results as JSONB on the filing record
        client.table("filings").update(
            {
                "status": FilingStatus.EXTRACTED.value,
                "raw_extraction_json": extraction_results,
                "extraction_model": settings.extraction_model,
                "extraction_tokens_used": total_tokens,
                "extracted_at": datetime.utcnow().isoformat(),
            }
        ).eq("id", filing_id).execute()

        # Store MD&A summary in agent_analyses for easy querying
        if mda_summary:
            summary_text = (
                mda_summary
                if isinstance(mda_summary, str)
                else json.dumps(mda_summary, indent=2, default=str)
            )

            client.table("agent_analyses").insert(
                {
                    "filing_id": filing_id,
                    "company_id": company_id,
                    "analysis_type": "quarterly_mda_summary",
                    "period_label": period_label,
                    "summary": summary_text[:500],
                    "full_analysis": summary_text,
                    "model_used": settings.extraction_model,
                    "tokens_used": total_tokens,
                }
            ).execute()

            logger.info("MD&A summary stored in agent_analyses for %s %s", ticker, period_label)

        # ==============================================================
        # Step 7: Mark complete
        # ==============================================================
        client.table("filings").update(
            {
                "status": FilingStatus.COMPLETED.value,
                "completed_at": datetime.utcnow().isoformat(),
            }
        ).eq("id", filing_id).execute()

        logger.info(
            "Successfully processed %s %s quarterly filing (%d sections, %d tokens)",
            ticker,
            period_label,
            len(extraction_results),
            total_tokens,
        )
        return True

    except Exception as e:
        logger.error("Failed to process %s %s: %s", ticker, period_label, str(e))
        if filing_id:
            client.table("filings").update(
                {
                    "status": FilingStatus.EXTRACTION_FAILED.value,
                    "error_message": str(e)[:1000],
                }
            ).eq("id", filing_id).execute()
        raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_sections(pdf_bytes: bytes) -> dict[str, str]:
    """
    Use pdfplumber to extract text from a 10-Q/10-K PDF, then identify
    and return the text for each key section.

    Returns a dict mapping section keys ('investment_schedule', 'derivatives',
    'mda') to their extracted text content.
    """
    pages_text: list[str] = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages_text.append(text)

    if not pages_text:
        logger.warning("pdfplumber extracted 0 pages of text")
        return {}

    logger.info("Extracted text from %d pages", len(pages_text))

    # Build a combined text with page markers for searching
    # We'll search for section headers and record which page they appear on
    section_starts: dict[str, int] = {}  # section_key -> start_page_index

    for page_idx, page_text in enumerate(pages_text):
        page_text_lower = page_text.lower()
        for section_key, patterns in SECTION_PATTERNS.items():
            # Only record the first occurrence of each section
            if section_key in section_starts:
                continue
            for pattern in patterns:
                if re.search(pattern, page_text_lower):
                    section_starts[section_key] = page_idx
                    logger.debug(
                        "Found '%s' section starting on page %d (pattern: %s)",
                        section_key,
                        page_idx + 1,
                        pattern,
                    )
                    break

    if not section_starts:
        logger.warning("No section headers matched in the PDF")
        return {}

    # Determine the end page for each section.
    # A section runs from its start page until the start of the next section
    # (sorted by page number), capped at MAX_SECTION_PAGES.
    sorted_sections = sorted(section_starts.items(), key=lambda x: x[1])
    total_pages = len(pages_text)

    sections: dict[str, str] = {}

    for i, (section_key, start_page) in enumerate(sorted_sections):
        # End page is the start of the next section, or end of document
        if i + 1 < len(sorted_sections):
            next_start = sorted_sections[i + 1][1]
        else:
            next_start = total_pages

        # Cap the section length
        end_page = min(start_page + MAX_SECTION_PAGES, next_start)

        section_text = "\n\n".join(pages_text[start_page:end_page])

        # Skip empty or very short sections (likely false positives)
        if len(section_text.strip()) < 200:
            logger.warning(
                "Section '%s' (pages %d-%d) has very little text (%d chars) — skipping",
                section_key,
                start_page + 1,
                end_page,
                len(section_text),
            )
            continue

        sections[section_key] = section_text
        logger.info(
            "Section '%s': pages %d-%d (%d chars)",
            section_key,
            start_page + 1,
            end_page,
            len(section_text),
        )

    return sections


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    reraise=True,
)
async def _extract_section_with_claude(
    section_text: str,
    system_prompt: str,
) -> tuple[dict | list | str, dict]:
    """
    Send a section of text to Claude for extraction/analysis.

    The system prompt determines what Claude extracts. For structured data
    prompts (investment schedule, derivatives), Claude returns JSON.
    For MD&A, Claude returns a narrative summary.

    Args:
        section_text: The extracted text for the section.
        system_prompt: The system prompt defining the extraction task.

    Returns:
        Tuple of (parsed result, metadata dict with token usage).
    """
    aclient = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    user_message = (
        "Extract the relevant data from the following section of a 10-Q/10-K filing. "
        "Return ONLY the JSON array or JSON object as specified in your instructions. "
        "If the section is a narrative analysis request, return your analysis as a JSON "
        "object with a 'summary' key and a 'key_points' array.\n\n"
        "---\n\n"
        f"{section_text}"
    )

    logger.debug(
        "Sending %d chars to Claude %s", len(section_text), settings.extraction_model
    )

    message = await aclient.messages.create(
        model=settings.extraction_model,
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    # Extract text from response
    response_text = ""
    for block in message.content:
        if block.type == "text":
            response_text += block.text

    # Clean up markdown fencing if present
    response_text = response_text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

    metadata = {
        "model": settings.extraction_model,
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }

    # Try to parse as JSON; if it fails, return raw text (for narrative MD&A responses)
    try:
        parsed = json.loads(response_text)
        return parsed, metadata
    except json.JSONDecodeError:
        logger.info(
            "Response is not JSON — returning as plain text (%d chars)",
            len(response_text),
        )
        return response_text, metadata
