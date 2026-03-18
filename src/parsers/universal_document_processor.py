"""
Universal document processor — full pipeline for non-ARMOUR documents.

1. Download (PDF/HTML)
2. Store in documents table + Supabase Storage
3. Run universal extraction
4. Store in universal_extractions table
5. Send email alert
"""

import hashlib
import logging
from datetime import date

import httpx

from src.config.company_registry import CompanyConfig
from src.config.settings import settings
from src.services.supabase_client import get_supabase_client

logger = logging.getLogger("mreit-monitor.universal_doc_processor")


def store_detected_document(
    company_id: str,
    ticker: str,
    source_url: str,
    document_type: str,
    document_date: date | None,
    title: str = "",
    period_label: str = "",
) -> None:
    """
    Store a detected document without downloading or extracting.

    Called by the scheduler when a new filing is found. Sets status="detected"
    so the user can review and approve processing from the Review page.
    """
    client = get_supabase_client()
    row = {
        "company_id": company_id,
        "document_type": document_type,
        "source_url": source_url,
        "title": title or f"{ticker} {document_type}",
        "document_date": document_date.isoformat() if document_date else None,
        "status": "detected",
    }
    if period_label:
        row["period_end"] = None  # will be set during processing
    client.table("company_documents_ML_REIT").upsert(
        row, on_conflict="company_id,document_type,source_url"
    ).execute()
    logger.info("Stored detected document: %s %s (%s)", ticker, document_type, source_url[:80])


async def process_document(
    company_id: str,
    company_name: str,
    ticker: str,
    company_config: CompanyConfig,
    source_url: str,
    document_type: str,
    document_date: date,
    period_label: str,
    title: str = "",
    skip_email: bool = False,
) -> bool:
    """
    Full processing pipeline for a universal document.

    Returns True on success, False on failure.
    """
    from src.agents.universal_extractor import extract_document, store_universal_extraction

    client = get_supabase_client()

    # Step 1: Download the document
    logger.info("Downloading %s for %s: %s", document_type, ticker, source_url)

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=60.0,
            headers={
                "User-Agent": settings.edgar_user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate",
            },
        ) as http_client:
            response = await http_client.get(source_url)
            response.raise_for_status()
    except Exception as e:
        logger.error("Download failed for %s: %s", source_url, e)
        return False

    content_type = response.headers.get("content-type", "")
    is_pdf = "pdf" in content_type.lower() or source_url.lower().endswith(".pdf")
    raw_content = response.content if is_pdf else response.text
    content_hash = hashlib.sha256(
        response.content if isinstance(response.content, bytes) else response.content.encode()
    ).hexdigest()

    # Step 2: Store in documents table
    doc_row = {
        "company_id": company_id,
        "document_type": document_type,
        "document_date": document_date.isoformat(),
        "title": title or f"{ticker} {document_type} {period_label}",
        "source_url": source_url,
        "content_hash": content_hash,
        "status": "downloaded",
    }

    # Only store text content (not PDF bytes) in raw_content
    if not is_pdf:
        doc_row["raw_content"] = raw_content if isinstance(raw_content, str) else raw_content.decode("utf-8", errors="replace")

    # Try to determine fiscal year/quarter from date
    if document_date:
        doc_row["fiscal_year"] = document_date.year
        month = document_date.month
        if month <= 3:
            doc_row["fiscal_quarter"] = 1
            doc_row["period_end"] = f"{document_date.year}-03-31"
        elif month <= 6:
            doc_row["fiscal_quarter"] = 2
            doc_row["period_end"] = f"{document_date.year}-06-30"
        elif month <= 9:
            doc_row["fiscal_quarter"] = 3
            doc_row["period_end"] = f"{document_date.year}-09-30"
        else:
            doc_row["fiscal_quarter"] = 4
            doc_row["period_end"] = f"{document_date.year}-12-31"

    try:
        result = (
            client.table("company_documents_ML_REIT")
            .upsert(doc_row, on_conflict="company_id,document_type,source_url")
            .execute()
        )
        document_id = result.data[0]["id"] if result.data else None
    except Exception as e:
        logger.error("Failed to store document record: %s", e)
        return False

    if not document_id:
        logger.error("No document ID returned after insert")
        return False

    # Step 3: Upload to Supabase Storage (PDF only)
    if is_pdf:
        try:
            storage_path = f"documents/{ticker}/{document_type}/{document_date.isoformat()}.pdf"
            client.storage.from_("filings").upload(
                storage_path,
                response.content,
                {"content-type": "application/pdf"},
            )
            client.table("company_documents_ML_REIT").update({"file_path": storage_path}).eq("id", document_id).execute()
            logger.info("Uploaded PDF to storage: %s", storage_path)
        except Exception as e:
            logger.warning("Storage upload failed (continuing): %s", e)

    # Step 4: Run universal extraction
    try:
        client.table("company_documents_ML_REIT").update({"status": "extracting"}).eq("id", document_id).execute()

        extraction, metadata = await extract_document(
            content=raw_content,
            document_type=document_type,
            company_config=company_config,
            source_url=source_url,
            is_pdf=is_pdf,
        )

        # Step 5: Store extraction
        await store_universal_extraction(extraction, document_id, company_id)

        client.table("company_documents_ML_REIT").update({"status": "extracted"}).eq("id", document_id).execute()

        logger.info(
            "Successfully extracted %s for %s (confidence=%.2f)",
            document_type, ticker, extraction.extraction_confidence,
        )

    except Exception as e:
        logger.error("Extraction failed for %s %s: %s", ticker, document_type, e)
        client.table("company_documents_ML_REIT").update({
            "status": "failed",
        }).eq("id", document_id).execute()
        return False

    # Step 6: Send email alert (best effort, skip for manual backfills)
    if not skip_email:
        try:
            from src.services.email_service import send_filing_alert

            await send_filing_alert(
                ticker=ticker,
                company_name=company_name,
                filing_type_label=document_type.replace("_", " ").title(),
                period_label=period_label,
                source_url=source_url,
            )
        except Exception as e:
            logger.warning("Email alert failed (non-blocking): %s", e)

    # Mark as completed
    client.table("company_documents_ML_REIT").update({"status": "completed"}).eq("id", document_id).execute()

    return True
