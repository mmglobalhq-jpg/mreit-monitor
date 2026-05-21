"""
DB-driven source loader — reads active scrape sources from reit_company_sources.

Replaces hardcoded ScrapeSource lists in company_registry.py for the IR scraping
pipeline. EDGAR sources continue to use the registry (CIK-based, not URL-based).
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger("mreit-monitor.source_loader")


@dataclass
class DBScrapeSource:
    """A scrape source loaded from reit_company_sources."""
    id: str
    ticker: str
    source_type: str  # "website" or "edgar"
    label: str
    url: str
    doc_type: str
    polling_frequency: str | None = None


_SOURCE_TYPE_TO_DOC_TYPE: dict[str, str] = {
    "monthly_update": "monthly_update",
    # annual_reports and quarterly_reports intentionally excluded — those come from EDGAR only
    "financial_results": "quarterly_earnings",
    "news": "press_release",
    "press_releases": "press_release",
    "presentations": "investor_presentation",
    "upcoming_events": "investor_presentation",
    "investor_relations": "investor_presentation",
    "investor_presentation": "investor_presentation",
    "supplement": "financial_supplement",
    "financial_supplement": "financial_supplement",
}


def load_active_website_sources(ticker: str | None = None) -> list[DBScrapeSource]:
    """
    Load active non-EDGAR sources from reit_company_sources.

    Returns all rows where active=true and source_type != 'edgar'.
    If ticker is provided, filters to that company only.
    """
    from src.services.supabase_client import get_supabase_client

    client = get_supabase_client()
    query = (
        client.table("reit_company_sources")
        .select("id, ticker, source_type, label, url, polling_frequency")
        .eq("active", True)
        .neq("source_type", "edgar")
    )
    if ticker:
        query = query.eq("ticker", ticker.upper())

    result = query.execute()
    sources = []
    for row in result.data:
        url = row.get("url") or ""
        if not url:
            continue
        source_type = row.get("source_type") or ""
        doc_type = _SOURCE_TYPE_TO_DOC_TYPE.get(source_type, source_type or "website_document")
        sources.append(DBScrapeSource(
            id=row["id"],
            ticker=row["ticker"],
            source_type=source_type,
            label=row.get("label") or "",
            url=url,
            doc_type=doc_type,
            polling_frequency=row.get("polling_frequency"),
        ))

    logger.debug(
        "Loaded %d active website sources%s",
        len(sources),
        f" for {ticker.upper()}" if ticker else "",
    )
    return sources
