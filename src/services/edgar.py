"""
SEC EDGAR submissions API client.

Polls the free data.sec.gov REST API for new filings by CIK.
No authentication required — just a User-Agent header with contact info.
"""

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime

import httpx

from src.config.settings import settings

logger = logging.getLogger("mreit-monitor.edgar")

EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{accession_with_dashes}-index.htm"

# Form types we care about
RELEVANT_FORM_TYPES = {"8-K", "10-Q", "10-K", "10-K/A", "10-Q/A"}

# Exhibit types we want to ingest (exclude XBRL schema/label/def/pre, graphics, full text)
INGEST_EXHIBIT_TYPES = {"EX-99.1", "EX-99.2", "EX-99.3"}


@dataclass
class EdgarFiling:
    """A filing detected from EDGAR submissions API."""
    accession_number: str
    form_type: str
    filing_date: date
    primary_document: str
    primary_document_url: str
    description: str


@dataclass
class ExhibitInfo:
    """An exhibit attachment found in an EDGAR filing index."""
    sequence: int
    description: str
    filename: str
    file_type: str   # e.g. "EX-99.1", "EX-101.SCH", "GRAPHIC"
    url: str
    size_bytes: int


async def get_filing_exhibits(accession_number: str, cik: str) -> list[ExhibitInfo]:
    """
    Fetch the EDGAR filing index page and return all document attachments.

    Args:
        accession_number: With dashes, e.g. '0001428205-26-000068'
        cik: CIK with leading zeros, e.g. '0001428205'

    Returns:
        List of ExhibitInfo for every document row in the filing index table.
    """
    cik_no_pad = cik.lstrip("0")
    accession_no_dashes = accession_number.replace("-", "")
    index_url = EDGAR_INDEX_URL.format(
        cik=cik_no_pad,
        accession_no_dashes=accession_no_dashes,
        accession_with_dashes=accession_number,
    )

    headers = {"User-Agent": settings.edgar_user_agent}
    logger.info("Fetching EDGAR filing index: %s", index_url)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(index_url, headers=headers)
        resp.raise_for_status()

    html = resp.text
    exhibits: list[ExhibitInfo] = []

    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) < 4:
            continue

        seq_text = re.sub(r"<[^>]+>", "", cells[0]).strip()
        if not seq_text.isdigit():
            continue

        description = re.sub(r"<[^>]+>", "", cells[1]).strip()

        href_match = re.search(r'href="([^"]+)"', cells[2])
        if not href_match:
            continue
        href = href_match.group(1)
        if href.startswith("/ix?doc="):
            href = href[len("/ix?doc="):]
        full_url = f"https://www.sec.gov{href}" if href.startswith("/") else href

        file_type = re.sub(r"<[^>]+>", "", cells[3]).strip()
        size_text = re.sub(r"<[^>]+>", "", cells[4]).strip() if len(cells) > 4 else "0"

        exhibits.append(ExhibitInfo(
            sequence=int(seq_text),
            description=description,
            filename=full_url.split("/")[-1],
            file_type=file_type,
            url=full_url,
            size_bytes=int(size_text) if size_text.isdigit() else 0,
        ))

    logger.info("Found %d documents in filing index %s", len(exhibits), accession_number)
    return exhibits


def accession_from_edgar_url(source_url: str) -> tuple[str, str] | None:
    """
    Parse CIK and accession_number (with dashes) from an EDGAR Archives URL.

    URL pattern: https://www.sec.gov/Archives/edgar/data/{cik}/{accno_nodash}/{file}
    Returns (cik_padded_10, accession_with_dashes) or None if not parseable.
    """
    match = re.match(
        r"https://www\.sec\.gov/Archives/edgar/data/(\d+)/(\d{18})/",
        source_url,
    )
    if not match:
        return None
    cik_raw = match.group(1)
    accno_nodash = match.group(2)
    cik_padded = cik_raw.zfill(10)
    accession = f"{accno_nodash[:10]}-{accno_nodash[10:12]}-{accno_nodash[12:]}"
    return cik_padded, accession


async def check_new_filings(
    cik: str,
    since_date: date | None = None,
) -> list[EdgarFiling]:
    """
    Check EDGAR for new filings from a company.
    
    Args:
        cik: The company's SEC CIK (with leading zeros, e.g., '0001428205')
        since_date: Only return filings after this date. If None, returns recent filings.
        
    Returns:
        List of EdgarFiling objects for new filings found
    """
    url = EDGAR_SUBMISSIONS_URL.format(cik=cik)
    headers = {
        "User-Agent": settings.edgar_user_agent,
        "Accept": "application/json",
    }
    
    logger.info("Checking EDGAR for new filings from CIK %s", cik)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
    
    data = response.json()
    
    # The recent filings are in data["filings"]["recent"]
    recent = data.get("filings", {}).get("recent", {})
    
    forms = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    accession_numbers = recent.get("accessionNumber", [])
    primary_documents = recent.get("primaryDocument", [])
    primary_doc_descriptions = recent.get("primaryDocDescription", [])
    
    filings = []
    for i in range(len(forms)):
        form_type = forms[i]
        if form_type not in RELEVANT_FORM_TYPES:
            continue
        
        filing_date_str = filing_dates[i]
        filing_dt = datetime.strptime(filing_date_str, "%Y-%m-%d").date()
        
        if since_date and filing_dt <= since_date:
            continue
        
        accession = accession_numbers[i]
        primary_doc = primary_documents[i]
        accession_no_dashes = accession.replace("-", "")
        
        doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession_no_dashes}/{primary_doc}"
        
        filings.append(EdgarFiling(
            accession_number=accession,
            form_type=form_type,
            filing_date=filing_dt,
            primary_document=primary_doc,
            primary_document_url=doc_url,
            description=primary_doc_descriptions[i] if i < len(primary_doc_descriptions) else "",
        ))
    
    logger.info("Found %d relevant filings from EDGAR for CIK %s", len(filings), cik)
    return filings
