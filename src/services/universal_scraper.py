"""
Universal scraper — uses a local LLM to parse any IR page and detect document links.

Instead of writing per-site CSS selectors, sends page HTML to Ollama/Qwen3:4b and
asks it to find all document links with dates, titles, and URLs. Works universally
across all company websites. Free — no API cost.
"""

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime

import httpx

from src.config.company_registry import CompanyConfig, ScrapeSource
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


def _build_scraper_prompt(html: str, page_url: str, doc_type: str, company_name: str) -> str:
    """Build the shared prompt for IR page document extraction."""
    # Truncate HTML if very large
    if len(html) > 150_000:
        html = html[:150_000] + "\n[TRUNCATED]"

    return f"""Analyze this investor relations page from {company_name} and find ALL document links.

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


def _parse_json_response(response_text: str, page_url: str) -> list[dict]:
    """Parse the LLM response text into a list of dicts."""
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
        logger.warning("Failed to parse LLM response for %s", page_url)
        results = []

    return results


def _parse_ir_page_with_bs4(html: str, page_url: str, doc_type: str) -> list[dict]:
    """
    Fast link extraction using BeautifulSoup. No LLM cost.
    Returns list of {url, title, date, period_label} dicts.
    """
    import re
    from datetime import date as date_cls
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    results = []
    seen_urls: set[str] = set()

    DOC_KEYWORDS = [
        "monthly", "update", "earnings",
        "press release", "investor presentation", "supplement",
        "results", "portfolio", "presentation",
    ]

    # Links matching these keywords are EDGAR-only — skip them on IR pages
    EDGAR_EXCLUDE_KEYWORDS = [
        "10-k", "10-q", "annual report", "proxy", "def 14a",
        "form 10", "sec filing", "8-k",
    ]

    # Navigation / utility links that are never documents — skip regardless of other matches
    NAV_EXCLUDE_KEYWORDS = [
        "financial calculator", "dividend history", "stock information",
        "stock price", "analyst coverage", "corporate governance",
        "contact us", "email alerts", "rss feed", "events calendar",
        "sec filings", "investor faq",
    ]

    DATE_PATTERNS = [
        r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}",
        r"q[1-4]\s+\d{4}",
        r"\d{1,2}/\d{1,2}/\d{4}",
        r"\d{4}-\d{2}-\d{2}",
    ]

    MONTH_MAP = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }

    for tag in soup.find_all("a", href=True):
        href = tag.get("href", "")
        text = tag.get_text(strip=True)
        full_url = urljoin(page_url, href)

        if not text or full_url in seen_urls:
            continue

        is_doc_link = (
            href.lower().endswith((".pdf", ".htm", ".html")) or
            any(kw in text.lower() for kw in DOC_KEYWORDS)
        )
        if not is_doc_link:
            continue

        if any(kw in text.lower() for kw in EDGAR_EXCLUDE_KEYWORDS):
            continue

        if any(kw in text.lower() for kw in NAV_EXCLUDE_KEYWORDS):
            continue

        # Build context by walking up to 3 ancestor elements to find a date
        context_text = text
        node = tag
        for _ in range(3):
            node = node.parent
            if node is None:
                break
            context_text = node.get_text(separator=" ", strip=True)
            # Stop walking up once we have enough text to search
            if len(context_text) > 500:
                break

        doc_date = None
        period_label = ""

        for pattern in DATE_PATTERNS:
            match = re.search(pattern, context_text.lower())
            if match:
                matched = match.group(0)
                month_match = re.match(r"(\w+)\s+(\d{4})", matched)
                if month_match:
                    month_name = month_match.group(1)
                    year = int(month_match.group(2))
                    if month_name in MONTH_MAP:
                        doc_date = date_cls(year, MONTH_MAP[month_name], 1)
                        period_label = f"{month_match.group(1).title()} {year}"
                        break
                q_match = re.match(r"q([1-4])\s+(\d{4})", matched)
                if q_match:
                    quarter = int(q_match.group(1))
                    year = int(q_match.group(2))
                    doc_date = date_cls(year, quarter * 3, 1)
                    period_label = f"Q{quarter} {year}"
                    break

        # Only include links where we could extract a date — prevents archive pages
        # from flooding the queue with undated historical links
        if doc_date is None:
            continue

        seen_urls.add(full_url)
        results.append({
            "url": full_url,
            "title": text,
            "date": doc_date.isoformat(),
            "period_label": period_label or text[:50],
        })

    return results


async def _parse_ir_page(
    html: str, page_url: str, doc_type: str, company_name: str,
) -> list[dict]:
    # Tier 1: BeautifulSoup — instant, no LLM
    results = _parse_ir_page_with_bs4(html, page_url, doc_type)
    if results:
        logger.info("BeautifulSoup found %d links on %s (no LLM needed)", len(results), page_url)
        return results

    # Tier 2: Qwen3 fallback — only when BS4 finds nothing
    logger.info("BeautifulSoup found nothing on %s — falling back to Qwen3", page_url)
    from src.agents.model_router import scrape_with_local_model
    prompt = _build_scraper_prompt(html, page_url, doc_type, company_name)
    response_text = await scrape_with_local_model(prompt)
    return _parse_json_response(response_text, page_url)


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

    html = ""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"},
        ) as client:
            response = await client.get(source.url)
            response.raise_for_status()
            html = response.text
    except Exception as e:
        logger.warning("httpx failed for %s (%s) — retrying with curl_cffi", source.url, e)
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate="chrome") as session:
                resp = await session.get(source.url, timeout=30)
                resp.raise_for_status()
                html = resp.text
        except Exception as e2:
            logger.error("Failed to fetch %s: %s", source.url, e2)
            return []

    try:
        raw_results = await _parse_ir_page(
            html=html,
            page_url=source.url,
            doc_type=source.doc_type,
            company_name=company_config.name,
        )
    except Exception as e:
        logger.error("Parsing failed for %s: %s", source.url, e)
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

    # Only keep 2025+ documents — older items on archive pages are already ingested or not needed
    detected = [d for d in detected if d.document_date.year >= 2025]

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
        client.table("reit_company_documents")
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
