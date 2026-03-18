"""
Universal scraper — uses Claude API to parse any IR page and detect document links.

Instead of writing per-site CSS selectors, sends page HTML to Claude and asks it
to find all document links with dates, titles, and URLs. Works universally across
all company websites.
"""

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime

import anthropic
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.company_registry import CompanyConfig, ScrapeSource
from src.config.settings import settings
from src.services.supabase_client import get_supabase_client

logger = logging.getLogger("mreit-monitor.universal_scraper")


@dataclass
class DetectedDocument:
    """A document link found on an IR page."""
    source_url: str
    document_type: str
    title: str
    document_date: date
    period_label: str
    source_page: str


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=4, max=15),
    reraise=True,
)
async def _parse_ir_page_with_claude(
    html: str,
    page_url: str,
    doc_type: str,
    company_name: str,
) -> list[dict]:
    """
    Send IR page HTML to Claude Sonnet and extract document links.

    Returns list of dicts with keys: url, title, date, period_label
    """
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Truncate HTML if very large
    if len(html) > 150_000:
        html = html[:150_000] + "\n[TRUNCATED]"

    prompt = f"""Analyze this investor relations page from {company_name} and find ALL document links.

I'm looking for documents of type: {doc_type}

For each document found, extract:
- url: The full URL to the document (resolve relative URLs using base: {page_url})
- title: The document title or description
- date: The date associated with the document (YYYY-MM-DD format)
- period_label: Human-readable period (e.g., "Q4 2025", "March 2026", "FY 2025")

Return a JSON array of objects. If no documents are found, return an empty array [].
Return ONLY the JSON array — no markdown, no commentary.

PAGE HTML:
{html}"""

    message = await client.messages.create(
        model=settings.scraper_model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
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
        results = json.loads(response_text)
        if not isinstance(results, list):
            results = []
    except json.JSONDecodeError:
        logger.warning("Failed to parse Claude response for %s", page_url)
        results = []

    return results


async def scrape_ir_page(
    source: ScrapeSource,
    company_config: CompanyConfig,
    ticker: str,
) -> list[DetectedDocument]:
    """
    Scrape a single IR page for documents.

    Args:
        source: ScrapeSource with url and doc_type
        company_config: CompanyConfig for the company
        ticker: Company ticker

    Returns:
        List of DetectedDocument objects
    """
    if not source.url:
        return []

    logger.info("Scraping %s for %s (%s)...", source.url, ticker, source.doc_type)

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": "mREIT-Monitor/1.0"},
        ) as client:
            response = await client.get(source.url)
            response.raise_for_status()
    except Exception as e:
        logger.error("Failed to fetch %s: %s", source.url, e)
        return []

    html = response.text

    # Use Claude to parse the page
    try:
        raw_results = await _parse_ir_page_with_claude(
            html=html,
            page_url=source.url,
            doc_type=source.doc_type,
            company_name=company_config.name,
        )
    except Exception as e:
        logger.error("Claude parsing failed for %s: %s", source.url, e)
        return []

    # Convert to DetectedDocument objects
    detected = []
    for item in raw_results:
        try:
            url = item.get("url", "")
            if not url:
                continue

            # Parse date
            date_str = item.get("date", "")
            try:
                doc_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                doc_date = date.today()

            detected.append(DetectedDocument(
                source_url=url,
                document_type=source.doc_type,
                title=item.get("title", ""),
                document_date=doc_date,
                period_label=item.get("period_label", ""),
                source_page=source.url,
            ))
        except Exception as e:
            logger.warning("Skipping invalid result from %s: %s", source.url, e)

    logger.info("Found %d documents on %s for %s", len(detected), source.url, ticker)
    return detected


async def scrape_company_universal(
    company_config: CompanyConfig,
    ticker: str,
) -> list[DetectedDocument]:
    """
    Scrape all website sources for a company using the universal Claude-based scraper.

    Args:
        company_config: CompanyConfig from registry
        ticker: Company ticker

    Returns:
        List of all detected documents across all sources
    """
    all_detected = []

    for source in company_config.scrape_sources:
        if source.type != "website":
            continue  # EDGAR is handled separately

        try:
            docs = await scrape_ir_page(source, company_config, ticker)
            all_detected.extend(docs)
        except Exception as e:
            logger.error("Failed to scrape %s for %s: %s", source.url, ticker, e)

    return all_detected


async def filter_new_documents(
    detected: list[DetectedDocument],
    company_id: str,
) -> list[DetectedDocument]:
    """
    Filter out documents that already exist in the documents table.
    """
    if not detected:
        return []

    client = get_supabase_client()
    urls = [d.source_url for d in detected]

    existing = (
        client.table("company_documents_ML_REIT")
        .select("source_url")
        .eq("company_id", company_id)
        .in_("source_url", urls)
        .execute()
    ).data

    existing_urls = {r["source_url"] for r in existing}
    new_docs = [d for d in detected if d.source_url not in existing_urls]

    if new_docs:
        logger.info(
            "Filtered %d detected → %d new documents (company %s)",
            len(detected), len(new_docs), company_id,
        )

    return new_docs
