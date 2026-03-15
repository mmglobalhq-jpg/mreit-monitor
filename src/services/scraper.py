"""
IR page scraper for detecting new filings on company investor relations pages.

Scrapes the monthly updates, quarterly reports, annual reports, and news pages
for each configured company. Compares found links against the filings table in
Supabase to identify new documents that need processing.
"""

import logging
import re
from dataclasses import dataclass
from datetime import date

import httpx
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from src.models.schemas import FilingType

logger = logging.getLogger("mreit-monitor.scraper")


@dataclass
class DetectedFiling:
    """A filing detected by the scraper but not yet downloaded."""
    source_url: str
    filing_type: FilingType
    filing_date: date
    period_label: str
    source_page: str


async def scrape_monthly_updates(
    page_url: str,
    link_pattern: str = "/static-files/",
) -> list[DetectedFiling]:
    """
    Scrape a company's monthly updates page for PDF links.
    
    For ARMOUR, the page structure is:
    - Date text (e.g., "3/13/2026")
    - Followed by an <a> tag with href containing "/static-files/{uuid}"
    - The <a> tag's title attribute has the PDF filename
    
    Args:
        page_url: URL of the monthly updates page
        link_pattern: Pattern to match in href attributes
        
    Returns:
        List of DetectedFiling objects for each PDF found
    """
    # TODO: Implement
    # 1. Fetch the page HTML with httpx
    # 2. Parse with BeautifulSoup
    # 3. Find all <a> tags with href matching link_pattern
    # 4. For each link, extract the date from the preceding text
    # 5. Build the full URL and create a DetectedFiling
    # 6. Return all detected filings
    
    logger.info("Scraping monthly updates from %s", page_url)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(page_url, follow_redirects=True)
        response.raise_for_status()
    
    soup = BeautifulSoup(response.text, "lxml")
    filings = []
    
    # Find all PDF links
    for link in soup.find_all("a", href=lambda h: h and link_pattern in h):
        href = link.get("href", "")
        title = link.get("title", "")
        
        # Build absolute URL
        if href.startswith("/"):
            from urllib.parse import urljoin
            href = urljoin(page_url, href)
        
        # Extract date from nearby text
        # The date is in the parent or sibling element
        # TODO: Implement date extraction logic specific to ARMOUR's page structure
        
        # Parse period label from title attribute
        # e.g., "March 2026 Company Update (1).pdf" → "March 2026"
        period_label = _extract_period_from_title(title)
        filing_date = _extract_date_from_context(link)
        
        if filing_date and period_label:
            filings.append(DetectedFiling(
                source_url=href,
                filing_type=FilingType.MONTHLY_UPDATE,
                filing_date=filing_date,
                period_label=period_label,
                source_page=page_url,
            ))
    
    logger.info("Found %d monthly update PDFs on %s", len(filings), page_url)
    return filings


async def scrape_quarterly_reports(page_url: str) -> list[DetectedFiling]:
    """
    Scrape a company's quarterly reports page for earnings releases,
    10-Q/10-K PDFs, and investor presentations.

    For ARMOUR, the page is organized by year (H2) → quarter (H3),
    with links for each document type within each quarter section.

    Returns:
        List of DetectedFiling objects for all documents found
    """
    from urllib.parse import urljoin

    logger.info("Scraping quarterly reports from %s", page_url)

    async with httpx.AsyncClient() as client:
        response = await client.get(page_url, follow_redirects=True)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    filings: list[DetectedFiling] = []

    # ARMOUR's page has year headings and quarter sub-headings.
    # Walk through the page collecting context as we encounter headings.
    current_year: int | None = None
    current_quarter_label: str | None = None
    current_quarter_num: int | None = None

    # Quarter label → approximate filing month (last month of quarter)
    _QUARTER_END_MONTH = {"Q1": 3, "Q2": 6, "Q3": 9, "Q4": 12}

    for element in soup.find_all(["h2", "h3", "a"]):
        tag_name = element.name

        if tag_name == "h2":
            # Year heading — extract 4-digit year
            text = element.get_text(strip=True)
            year_match = re.search(r"(\d{4})", text)
            if year_match:
                current_year = int(year_match.group(1))
                current_quarter_label = None
            continue

        if tag_name == "h3":
            # Quarter heading — e.g. "Fourth Quarter 2025" or "Q4 2025"
            text = element.get_text(strip=True)
            # Try explicit Q-label first
            q_match = re.search(r"(Q[1-4])\s*(\d{4})", text, re.IGNORECASE)
            if q_match:
                q_label = q_match.group(1).upper()
                year = int(q_match.group(2))
                current_quarter_label = f"{q_label} {year}"
                current_year = year
                current_quarter_num = _QUARTER_END_MONTH.get(q_label)
            else:
                # Try ordinal quarter names: "First Quarter 2025", etc.
                ordinal_map = {
                    "first": "Q1", "second": "Q2", "third": "Q3", "fourth": "Q4",
                    "1st": "Q1", "2nd": "Q2", "3rd": "Q3", "4th": "Q4",
                }
                for word, q_label in ordinal_map.items():
                    if word in text.lower():
                        year_match2 = re.search(r"(\d{4})", text)
                        if year_match2:
                            year = int(year_match2.group(1))
                            current_quarter_label = f"{q_label} {year}"
                            current_year = year
                            current_quarter_num = _QUARTER_END_MONTH.get(q_label)
                        break
            continue

        # It's an <a> tag — classify the link
        if current_year is None or current_quarter_label is None:
            continue

        href = element.get("href", "")
        link_text = element.get_text(strip=True).lower()

        # Skip webcasts
        if "webcast" in link_text:
            continue

        # Skip empty hrefs
        if not href or href == "#":
            continue

        # Determine filing type from link text
        filing_type: FilingType | None = None
        if "earnings release" in link_text or "earnings" in link_text and "release" in link_text:
            filing_type = FilingType.EARNINGS_RELEASE
        elif "10-k" in link_text:
            filing_type = FilingType.ANNUAL_10K
        elif "10-q" in link_text:
            filing_type = FilingType.QUARTERLY_10Q
        elif "investor presentation" in link_text or "presentation" in link_text:
            filing_type = FilingType.INVESTOR_PRESENTATION
        else:
            # Skip links we don't recognize (e.g., transcript, supplement)
            continue

        # Build absolute URL
        if href.startswith("/"):
            href = urljoin(page_url, href)

        # Derive a filing date from the quarter label
        filing_date_val = _derive_quarter_date(current_year, current_quarter_num)

        filings.append(DetectedFiling(
            source_url=href,
            filing_type=filing_type,
            filing_date=filing_date_val,
            period_label=current_quarter_label,
            source_page=page_url,
        ))

    logger.info("Found %d quarterly report items on %s", len(filings), page_url)
    return filings


async def scrape_news_page(news_url: str) -> list[DetectedFiling]:
    """
    Scrape a company's news page for earnings releases and other announcements.

    Looks for news release links whose headlines mention earnings, dividends,
    or quarterly results.

    Returns:
        List of DetectedFiling objects for news items found
    """
    from urllib.parse import urljoin

    logger.info("Scraping news from %s", news_url)

    async with httpx.AsyncClient() as client:
        response = await client.get(news_url, follow_redirects=True)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    filings: list[DetectedFiling] = []

    # Keywords that indicate earnings or dividend news
    _EARNINGS_KEYWORDS = re.compile(
        r"(?:Q[1-4]|results|dividend|earnings|quarterly|annual)", re.IGNORECASE
    )

    # Find links that point to /news-releases/ paths
    for link in soup.find_all("a", href=lambda h: h and "/news-releases/" in h):
        href = link.get("href", "")
        link_text = link.get_text(strip=True)

        if not link_text or not _EARNINGS_KEYWORDS.search(link_text):
            continue

        # Build absolute URL
        if href.startswith("/"):
            href = urljoin(news_url, href)

        # Determine filing type from headline
        lower_text = link_text.lower()
        if "dividend" in lower_text:
            filing_type = FilingType.OTHER
        elif any(kw in lower_text for kw in ("results", "earnings", "q1", "q2", "q3", "q4")):
            filing_type = FilingType.EARNINGS_RELEASE
        else:
            filing_type = FilingType.OTHER

        # Extract date from context around the link
        filing_date_val = _extract_date_from_context(link)

        # Try to extract a period label from the headline (e.g., "Q4 2025")
        period_label = ""
        q_match = re.search(r"(Q[1-4])\s*(\d{4})", link_text, re.IGNORECASE)
        if q_match:
            period_label = f"{q_match.group(1).upper()} {q_match.group(2)}"
        else:
            # Fall back to month/year in the headline
            m_match = _MONTH_YEAR_PATTERN.search(link_text)
            if m_match:
                period_label = f"{m_match.group(1)} {m_match.group(2)}"

        # If we couldn't get a date from context, use today as fallback
        if filing_date_val is None:
            filing_date_val = date.today()

        filings.append(DetectedFiling(
            source_url=href,
            filing_type=filing_type,
            filing_date=filing_date_val,
            period_label=period_label,
            source_page=news_url,
        ))

    logger.info("Found %d news items on %s", len(filings), news_url)
    return filings


async def filter_new_filings(
    detected: list[DetectedFiling],
    company_id: str,
) -> list[DetectedFiling]:
    """
    Filter out filings that are already in the database.
    
    Checks the filings table in Supabase for existing records
    with matching company_id + source_url.
    """
    # TODO: Implement
    # 1. Get all existing source_urls for this company from Supabase
    # 2. Filter detected list to only include URLs not in the database
    
    from src.services.supabase_client import get_supabase_client
    
    client = get_supabase_client()
    existing = client.table("filings").select("source_url").eq("company_id", company_id).execute()
    existing_urls = {r["source_url"] for r in existing.data}
    
    new_filings = [f for f in detected if f.source_url not in existing_urls]
    logger.info("Found %d new filings out of %d detected", len(new_filings), len(detected))
    return new_filings


_MONTHS_RE = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
_MONTH_YEAR_PATTERN = re.compile(rf"({_MONTHS_RE})\s+(\d{{4}})")
_DATE_PATTERN = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")


def _derive_quarter_date(year: int | None, quarter_end_month: int | None) -> date:
    """Derive an approximate filing date from a year and quarter end month.

    Returns the last day of the quarter-end month, or today as a fallback.
    """
    if year is None or quarter_end_month is None:
        return date.today()
    import calendar
    last_day = calendar.monthrange(year, quarter_end_month)[1]
    return date(year, quarter_end_month, last_day)


def _extract_period_from_title(title: str) -> str | None:
    """Extract period label from PDF title, e.g., 'March 2026 Company Update (1).pdf' → 'March 2026'."""
    if not title:
        return None
    # Look for "Month Year" pattern
    match = _MONTH_YEAR_PATTERN.search(title)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    # Fallback: try YYYY-MM pattern
    ym_match = re.search(r"(\d{4})-(\d{2})", title)
    if ym_match:
        try:
            dt = dateutil_parser.parse(f"{ym_match.group(1)}-{ym_match.group(2)}-01")
            return dt.strftime("%B %Y")
        except ValueError:
            pass
    return None


def _extract_date_from_context(link_element) -> date | None:
    """Extract the posting date from the HTML context around a link element."""
    # Strategy 1: Check parent element's text for a date pattern (MM/DD/YYYY)
    parent = link_element.parent
    if parent:
        parent_text = parent.get_text(separator=" ", strip=True)
        match = _DATE_PATTERN.search(parent_text)
        if match:
            try:
                return dateutil_parser.parse(match.group()).date()
            except (ValueError, TypeError):
                pass

    # Strategy 2: Check previous siblings
    for sibling in link_element.previous_siblings:
        sib_text = sibling.string if hasattr(sibling, "string") and sibling.string else str(sibling)
        match = _DATE_PATTERN.search(sib_text)
        if match:
            try:
                return dateutil_parser.parse(match.group()).date()
            except (ValueError, TypeError):
                pass

    # Strategy 3: Walk up to grandparent and look for date
    if parent and parent.parent:
        gp_text = parent.parent.get_text(separator=" ", strip=True)
        match = _DATE_PATTERN.search(gp_text)
        if match:
            try:
                return dateutil_parser.parse(match.group()).date()
            except (ValueError, TypeError):
                pass

    # Strategy 4: Derive date from title attribute "Month YYYY" → first of month
    title = link_element.get("title", "")
    month_match = _MONTH_YEAR_PATTERN.search(title)
    if month_match:
        try:
            return dateutil_parser.parse(f"{month_match.group(1)} 1 {month_match.group(2)}").date()
        except (ValueError, TypeError):
            pass

    return None


async def scrape_company(company: dict) -> list[DetectedFiling]:
    """
    Orchestrate scraping for a single company across all configured page types.

    Args:
        company: Company record from Supabase (must have scrape_config or hardcoded URLs)

    Returns:
        Aggregated list of DetectedFiling objects
    """
    from src.config.companies import COMPANY_CONFIGS

    ticker = company["ticker"]
    config = COMPANY_CONFIGS.get(ticker, {})
    all_filings: list[DetectedFiling] = []

    # Scrape monthly updates
    monthly_url = config.get("monthly_updates_url")
    if monthly_url:
        try:
            monthly = await scrape_monthly_updates(
                monthly_url,
                link_pattern=config.get("monthly_pdf_link_pattern", "/static-files/"),
            )
            all_filings.extend(monthly)
        except Exception as e:
            logger.error("Failed to scrape monthly updates for %s: %s", ticker, e)

    # Scrape quarterly reports
    quarterly_url = config.get("quarterly_reports_url")
    if quarterly_url:
        try:
            quarterly = await scrape_quarterly_reports(quarterly_url)
            all_filings.extend(quarterly)
        except Exception as e:
            logger.error("Failed to scrape quarterly reports for %s: %s", ticker, e)

    # Scrape news page
    news_url = config.get("news_url")
    if news_url:
        try:
            news = await scrape_news_page(news_url)
            all_filings.extend(news)
        except Exception as e:
            logger.error("Failed to scrape news page for %s: %s", ticker, e)

    logger.info("Scrape complete for %s: %d total filings detected", ticker, len(all_filings))
    return all_filings
