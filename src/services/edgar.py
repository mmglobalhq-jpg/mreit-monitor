"""
SEC EDGAR submissions API client.

Polls the free data.sec.gov REST API for new filings by CIK.
No authentication required — just a User-Agent header with contact info.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime

import httpx

from src.config.settings import settings

logger = logging.getLogger("mreit-monitor.edgar")

EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

# Form types we care about
RELEVANT_FORM_TYPES = {"8-K", "10-Q", "10-K", "10-K/A", "10-Q/A"}


@dataclass
class EdgarFiling:
    """A filing detected from EDGAR submissions API."""
    accession_number: str
    form_type: str
    filing_date: date
    primary_document: str
    primary_document_url: str
    description: str


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
