"""
Document downloader — fetches PDFs/HTML from source URLs
and uploads them to Supabase Storage.
"""

import logging
from datetime import datetime

import httpx

from src.services.supabase_client import get_supabase_client

logger = logging.getLogger("mreit-monitor.downloader")


async def download_pdf(url: str) -> bytes:
    """Download a PDF from a URL and return the raw bytes."""
    logger.info("Downloading PDF from %s", url)
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        response = await client.get(url)
        response.raise_for_status()
    
    content_type = response.headers.get("content-type", "")
    if "pdf" not in content_type and not url.endswith(".pdf"):
        logger.warning("URL may not be a PDF (content-type: %s): %s", content_type, url)
    
    logger.info("Downloaded %d bytes from %s", len(response.content), url)
    return response.content


async def download_html(url: str) -> str:
    """Download an HTML page and return the text content."""
    logger.info("Downloading HTML from %s", url)
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
    return response.text


async def upload_to_storage(
    file_bytes: bytes,
    storage_path: str,
    bucket: str = "filings",
    content_type: str = "application/pdf",
) -> str:
    """
    Upload a file to Supabase Storage.
    
    Args:
        file_bytes: Raw file bytes
        storage_path: Path within the bucket (e.g., 'armour/monthly/2026-03.pdf')
        bucket: Storage bucket name
        content_type: MIME type
        
    Returns:
        The storage path (for reference in the filings table)
    """
    client = get_supabase_client()
    
    logger.info("Uploading %d bytes to storage: %s/%s", len(file_bytes), bucket, storage_path)
    
    # Upload to Supabase Storage
    client.storage.from_(bucket).upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": content_type},
    )
    
    logger.info("Upload complete: %s/%s", bucket, storage_path)
    return storage_path


def build_storage_path(ticker: str, filing_type: str, period_label: str) -> str:
    """
    Build a storage path for a filing.
    
    Examples:
        - armour/monthly/2026-03.pdf
        - armour/quarterly/Q4-2025-10K.pdf
        - armour/earnings/Q4-2025.html
    """
    ticker_lower = ticker.lower()
    safe_period = period_label.replace(" ", "-").replace("/", "-")
    
    if filing_type == "monthly_update":
        return f"{ticker_lower}/monthly/{safe_period}.pdf"
    elif filing_type in ("quarterly_10q", "annual_10k"):
        return f"{ticker_lower}/quarterly/{safe_period}.pdf"
    elif filing_type == "earnings_release":
        return f"{ticker_lower}/earnings/{safe_period}.html"
    elif filing_type == "investor_presentation":
        return f"{ticker_lower}/presentations/{safe_period}.pdf"
    else:
        return f"{ticker_lower}/other/{safe_period}-{datetime.utcnow().strftime('%Y%m%d')}"
