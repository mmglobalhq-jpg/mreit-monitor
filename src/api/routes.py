"""
API routes for health checks, manual triggers, status queries, and summary reports.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger("mreit-monitor.api")


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    environment: str


class TriggerResponse(BaseModel):
    status: str
    message: str
    filings_found: int = 0


class FilingStatusResponse(BaseModel):
    ticker: str
    filing_type: str
    period_label: str
    status: str
    filing_date: str
    processed_at: str | None = None


# ============================================================================
# Health
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check():
    from src.config.settings import settings
    return HealthResponse(
        status="ok",
        timestamp=datetime.utcnow().isoformat(),
        environment=settings.environment,
    )


# ============================================================================
# Manual Triggers
# ============================================================================

@router.post("/trigger/poll/{ticker}", response_model=TriggerResponse)
async def trigger_poll(ticker: str):
    """Manually trigger a poll for a specific company. Works for all tickers."""
    from src.config.company_registry import get_company_config
    from src.models.database import get_company_by_ticker
    from src.services.scraper import scrape_company, filter_new_filings
    from src.parsers.monthly_update import process_monthly_update

    logger.info("Manual poll triggered for %s", ticker.upper())

    company = get_company_by_ticker(ticker)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company {ticker.upper()} not found")

    registry_config = get_company_config(ticker)

    # ARMOUR uses existing scraper; other companies use universal scraper
    if ticker.upper() == "ARR":
        detected = await scrape_company(company)
        new_filings = await filter_new_filings(detected, company["id"])

        processed = 0
        for filing in new_filings:
            if filing.filing_type.value == "monthly_update":
                try:
                    await process_monthly_update(
                        company_id=company["id"],
                        company_name=company["name"],
                        ticker=company["ticker"],
                        source_url=filing.source_url,
                        filing_date=filing.filing_date,
                        period_label=filing.period_label,
                    )
                    processed += 1
                except Exception as e:
                    logger.error("Failed to process %s: %s", filing.period_label, e)

        return TriggerResponse(
            status="ok",
            message=f"Poll complete. {len(detected)} detected, {len(new_filings)} new, {processed} processed.",
            filings_found=len(new_filings),
        )

    elif registry_config:
        from src.services.universal_scraper import scrape_company_universal, filter_new_documents
        from src.parsers.universal_document_processor import process_document

        detected = await scrape_company_universal(registry_config, ticker.upper())
        new_docs = await filter_new_documents(detected, company["id"])

        processed = 0
        for doc in new_docs:
            try:
                success = await process_document(
                    company_id=company["id"],
                    company_name=company["name"],
                    ticker=company["ticker"],
                    company_config=registry_config,
                    source_url=doc.source_url,
                    document_type=doc.document_type,
                    document_date=doc.document_date,
                    period_label=doc.period_label,
                    title=doc.title,
                )
                if success:
                    processed += 1
            except Exception as e:
                logger.error("Failed to process %s: %s", doc.period_label, e)

        return TriggerResponse(
            status="ok",
            message=f"Poll complete. {len(detected)} detected, {len(new_docs)} new, {processed} processed.",
            filings_found=len(new_docs),
        )

    else:
        raise HTTPException(status_code=400, detail=f"No configuration for {ticker.upper()}")


class ExtractRequest(BaseModel):
    ticker: str
    source_url: str
    document_type: str = "quarterly_earnings"


@router.post("/trigger/process")
async def trigger_process(source_url: str, ticker: str = "ARR", filing_type: str = "monthly_update"):
    """Manually process a specific filing by URL."""
    from src.config.company_registry import get_company_config
    from src.models.database import get_company_by_ticker
    from src.parsers.monthly_update import process_monthly_update

    logger.info("Manual process triggered for %s (%s)", source_url, ticker.upper())

    company = get_company_by_ticker(ticker)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company {ticker.upper()} not found")

    if filing_type == "monthly_update" and ticker.upper() == "ARR":
        success = await process_monthly_update(
            company_id=company["id"],
            company_name=company["name"],
            ticker=company["ticker"],
            source_url=source_url,
            filing_date=datetime.utcnow().date(),
            period_label="Manual Processing",
        )
        return TriggerResponse(
            status="ok" if success else "error",
            message=f"Processing {'completed' if success else 'failed'} for {source_url}",
            filings_found=1,
        )
    else:
        # Use universal pipeline
        registry_config = get_company_config(ticker)
        if not registry_config:
            raise HTTPException(status_code=400, detail=f"No config for {ticker.upper()}")

        from src.parsers.universal_document_processor import process_document
        success = await process_document(
            company_id=company["id"],
            company_name=company["name"],
            ticker=company["ticker"],
            company_config=registry_config,
            source_url=source_url,
            document_type=filing_type,
            document_date=datetime.utcnow().date(),
            period_label="Manual Processing",
        )
        return TriggerResponse(
            status="ok" if success else "error",
            message=f"Processing {'completed' if success else 'failed'} for {source_url}",
            filings_found=1,
        )


@router.post("/trigger/extract")
async def trigger_extract(request: ExtractRequest):
    """Run universal extraction on a specific URL for any company."""
    from src.config.company_registry import get_company_config
    from src.models.database import get_company_by_ticker
    from src.parsers.universal_document_processor import process_document

    logger.info("Extract triggered for %s: %s", request.ticker.upper(), request.source_url)

    company = get_company_by_ticker(request.ticker)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company {request.ticker.upper()} not found")

    registry_config = get_company_config(request.ticker)
    if not registry_config:
        raise HTTPException(status_code=400, detail=f"No config for {request.ticker.upper()}")

    success = await process_document(
        company_id=company["id"],
        company_name=company["name"],
        ticker=company["ticker"],
        company_config=registry_config,
        source_url=request.source_url,
        document_type=request.document_type,
        document_date=datetime.utcnow().date(),
        period_label="Manual Extraction",
    )

    return TriggerResponse(
        status="ok" if success else "error",
        message=f"Extraction {'completed' if success else 'failed'} for {request.source_url}",
        filings_found=1 if success else 0,
    )


@router.post("/trigger/backfill/{ticker}", response_model=TriggerResponse)
async def trigger_backfill(ticker: str):
    """Trigger historical backfill for a company."""
    import asyncio

    logger.info("Backfill triggered for %s", ticker.upper())

    if ticker.upper() == "ARR":
        from scripts.backfill_armour import run_backfill
        asyncio.create_task(run_backfill())
    else:
        # For non-ARMOUR companies, run a universal poll as the "backfill"
        # (scrapes all available documents from their IR pages)
        from src.config.company_registry import get_company_config
        from src.models.database import get_company_by_ticker

        company = get_company_by_ticker(ticker)
        if not company:
            raise HTTPException(status_code=404, detail=f"Company {ticker.upper()} not found")

        registry_config = get_company_config(ticker)
        if not registry_config:
            raise HTTPException(status_code=400, detail=f"No config for {ticker.upper()}")

        async def _backfill():
            from src.services.universal_scraper import scrape_company_universal, filter_new_documents
            from src.parsers.universal_document_processor import process_document

            docs = await scrape_company_universal(registry_config, ticker.upper())
            new_docs = await filter_new_documents(docs, company["id"])
            logger.info("Backfill for %s: %d docs detected, %d new", ticker.upper(), len(docs), len(new_docs))

            for doc in new_docs:
                try:
                    await process_document(
                        company_id=company["id"],
                        company_name=company["name"],
                        ticker=company["ticker"],
                        company_config=registry_config,
                        source_url=doc.source_url,
                        document_type=doc.document_type,
                        document_date=doc.document_date,
                        period_label=doc.period_label,
                        title=doc.title,
                    )
                except Exception as e:
                    logger.error("Backfill failed for %s %s: %s", ticker.upper(), doc.source_url, e)

            logger.info("Backfill complete for %s", ticker.upper())

        asyncio.create_task(_backfill())

    return TriggerResponse(
        status="ok",
        message=f"Backfill started for {ticker.upper()} in background",
        filings_found=0,
    )


# ============================================================================
# Status Queries
# ============================================================================

@router.get("/status/latest/{ticker}")
async def get_latest_filing(ticker: str):
    """Get the most recently processed filing for a company."""
    from src.models.database import get_company_by_ticker, get_latest_filing as db_get_latest

    company = get_company_by_ticker(ticker)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company {ticker.upper()} not found")

    filing = db_get_latest(company["id"])
    if not filing:
        raise HTTPException(status_code=404, detail=f"No filings found for {ticker.upper()}")

    return FilingStatusResponse(
        ticker=ticker.upper(),
        filing_type=filing["filing_type"],
        period_label=filing["period_label"],
        status=filing["status"],
        filing_date=filing["filing_date"],
        processed_at=filing.get("completed_at"),
    )


@router.get("/status/filings/{ticker}")
async def list_filings(ticker: str, filing_type: str | None = None, limit: int = 20):
    """List processed filings for a company."""
    from src.models.database import get_company_by_ticker
    from src.services.supabase_client import get_supabase_client

    company = get_company_by_ticker(ticker)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company {ticker.upper()} not found")

    client = get_supabase_client()
    query = (
        client.table("filings")
        .select("filing_type, period_label, status, filing_date, completed_at")
        .eq("company_id", company["id"])
        .order("filing_date", desc=True)
        .limit(limit)
    )
    if filing_type:
        query = query.eq("filing_type", filing_type)

    result = query.execute()

    return [
        FilingStatusResponse(
            ticker=ticker.upper(),
            filing_type=r["filing_type"],
            period_label=r["period_label"],
            status=r["status"],
            filing_date=r["filing_date"],
            processed_at=r.get("completed_at"),
        )
        for r in result.data
    ]


# ============================================================================
# Summary Reports
# ============================================================================

class MonthlySummaryRequest(BaseModel):
    ticker: str
    year: int
    month: int


class QuarterlySummaryRequest(BaseModel):
    ticker: str
    year: int
    quarter: int


class AnnualSummaryRequest(BaseModel):
    ticker: str
    year: int


class InvestorMaterialRequest(BaseModel):
    ticker: str
    document_id: str


@router.post("/summary/monthly")
async def generate_monthly_summary(request: MonthlySummaryRequest):
    """Generate a monthly summary report."""
    from src.models.database import get_company_by_ticker
    from src.services.summary_service import generate_monthly_summary as gen_monthly

    company = get_company_by_ticker(request.ticker)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company {request.ticker.upper()} not found")

    if not 1 <= request.month <= 12:
        raise HTTPException(status_code=400, detail="Month must be 1-12")

    try:
        result = await gen_monthly(
            company_id=company["id"],
            company_name=company["name"],
            ticker=company["ticker"],
            year=request.year,
            month=request.month,
        )
        return {"status": "ok", "report": result}
    except Exception as e:
        logger.error("Failed to generate monthly summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summary/quarterly")
async def generate_quarterly_summary(request: QuarterlySummaryRequest):
    """Generate a quarterly summary report."""
    from src.models.database import get_company_by_ticker
    from src.services.summary_service import generate_quarterly_summary as gen_quarterly

    company = get_company_by_ticker(request.ticker)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company {request.ticker.upper()} not found")

    if not 1 <= request.quarter <= 4:
        raise HTTPException(status_code=400, detail="Quarter must be 1-4")

    try:
        result = await gen_quarterly(
            company_id=company["id"],
            company_name=company["name"],
            ticker=company["ticker"],
            year=request.year,
            quarter=request.quarter,
        )
        return {"status": "ok", "report": result}
    except Exception as e:
        logger.error("Failed to generate quarterly summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summary/annual")
async def generate_annual_summary(request: AnnualSummaryRequest):
    """Generate an annual summary report."""
    from src.models.database import get_company_by_ticker
    from src.services.summary_service import generate_annual_summary as gen_annual

    company = get_company_by_ticker(request.ticker)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company {request.ticker.upper()} not found")

    try:
        result = await gen_annual(
            company_id=company["id"],
            company_name=company["name"],
            ticker=company["ticker"],
            year=request.year,
        )
        return {"status": "ok", "report": result}
    except Exception as e:
        logger.error("Failed to generate annual summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summary/investor-material")
async def analyze_investor_material(request: InvestorMaterialRequest):
    """Analyze an investor material document."""
    from src.models.database import get_company_by_ticker
    from src.services.summary_service import analyze_material

    company = get_company_by_ticker(request.ticker)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company {request.ticker.upper()} not found")

    try:
        result = await analyze_material(
            company_id=company["id"],
            company_name=company["name"],
            ticker=company["ticker"],
            document_id=request.document_id,
        )
        return {"status": "ok", "analysis": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to analyze investor material: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary/latest/{ticker}")
async def get_latest_summary(ticker: str):
    """Get the most recent summary report for a company."""
    from src.models.database import get_company_by_ticker
    from src.services.supabase_client import get_supabase_client

    company = get_company_by_ticker(ticker)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company {ticker.upper()} not found")

    client = get_supabase_client()
    result = (
        client.table("summary_reports")
        .select("*")
        .eq("company_id", company["id"])
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail=f"No summary reports found for {ticker.upper()}")

    return result.data[0]
