"""
Frontend API routes — clean JSON endpoints for the Next.js frontend.

All endpoints require X-API-Key header authentication.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from src.config.settings import settings

logger = logging.getLogger("mreit-monitor.frontend_api")

api_router = APIRouter(prefix="/api", tags=["frontend"])

# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(key: str | None = Security(_api_key_header)):
    if not settings.reit_monitor_api_key:
        return  # auth disabled when key not configured
    if key != settings.reit_monitor_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ---------------------------------------------------------------------------
# 1. GET /api/companies
# ---------------------------------------------------------------------------

@api_router.get("/companies", dependencies=[Depends(require_api_key)])
async def list_companies():
    """Return all active companies with their registry config."""
    from src.config.company_registry import COMPANY_REGISTRY
    from src.models.database import get_active_companies

    db_companies = get_active_companies()
    result = []
    for co in db_companies:
        ticker = co["ticker"]
        registry = COMPANY_REGISTRY.get(ticker)
        entry = {
            "id": co["id"],
            "ticker": ticker,
            "name": co["name"],
            "cik": co.get("cik"),
            "is_active": co.get("is_active", True),
            "created_at": co.get("created_at"),
        }
        if registry:
            entry["config"] = {
                "document_types": registry.document_types,
                "primary_focus": registry.primary_focus,
                "has_monthly_update": registry.has_monthly_update,
                "has_financial_supplement": registry.has_financial_supplement,
                "has_investor_presentation": registry.has_investor_presentation,
                "check_cadence": registry.check_cadence,
                "notes": registry.notes,
            }
        result.append(entry)
    return result


# ---------------------------------------------------------------------------
# 2. GET /api/reports
# ---------------------------------------------------------------------------

@api_router.get("/reports", dependencies=[Depends(require_api_key)])
async def list_reports(
    company: str | None = Query(None, description="Ticker filter"),
    type: str | None = Query(None, description="monthly|quarterly|annual"),
    limit: int = Query(20, ge=1, le=100),
):
    """List summary reports, optionally filtered by company and type."""
    from src.models.database import get_company_by_ticker
    from src.services.supabase_client import get_supabase_client

    client = get_supabase_client()
    query = (
        client.table("summary_reports_ML_REIT")
        .select("id, company_id, report_type, period_label, period_start, period_end, model_used, tokens_used, email_sent, created_at, report_json")
        .order("created_at", desc=True)
        .limit(limit)
    )

    if company:
        co = get_company_by_ticker(company)
        if not co:
            raise HTTPException(status_code=404, detail=f"Company {company.upper()} not found")
        query = query.eq("company_id", co["id"])

    if type:
        query = query.eq("report_type", type)

    result = query.execute()

    # Enrich with ticker from report_json
    reports = []
    for r in result.data:
        rj = r.get("report_json") or {}
        reports.append({
            "id": r["id"],
            "ticker": rj.get("ticker", ""),
            "company_name": rj.get("company_name", ""),
            "report_type": r["report_type"],
            "period_label": r["period_label"],
            "period_start": r.get("period_start"),
            "period_end": r.get("period_end"),
            "model_used": r.get("model_used"),
            "tokens_used": r.get("tokens_used"),
            "email_sent": r.get("email_sent", False),
            "created_at": r.get("created_at"),
            # Include the overall summary snippet for list views
            "overall_summary": (rj.get("overall_summary", {}).get("content") or "")[:500],
        })
    return reports


# ---------------------------------------------------------------------------
# 3. GET /api/reports/{id}
# ---------------------------------------------------------------------------

@api_router.get("/reports/latest", dependencies=[Depends(require_api_key)])
async def latest_reports(
    company: str = Query(..., description="Ticker"),
):
    """Return the most recent report per type for a company."""
    from src.models.database import get_company_by_ticker
    from src.services.supabase_client import get_supabase_client

    co = get_company_by_ticker(company)
    if not co:
        raise HTTPException(status_code=404, detail=f"Company {company.upper()} not found")

    client = get_supabase_client()
    latest = {}
    for rtype in ("monthly", "quarterly", "annual"):
        result = (
            client.table("summary_reports_ML_REIT")
            .select("id, report_type, period_label, period_start, period_end, model_used, tokens_used, email_sent, created_at, report_json")
            .eq("company_id", co["id"])
            .eq("report_type", rtype)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            r = result.data[0]
            rj = r.get("report_json") or {}
            latest[rtype] = {
                "id": r["id"],
                "ticker": rj.get("ticker", company.upper()),
                "company_name": rj.get("company_name", co["name"]),
                "report_type": r["report_type"],
                "period_label": r["period_label"],
                "created_at": r.get("created_at"),
                "overall_summary": (rj.get("overall_summary", {}).get("content") or "")[:500],
            }
    return latest


@api_router.get("/reports/{report_id}", dependencies=[Depends(require_api_key)])
async def get_report(report_id: str):
    """Get a single full report with report_json."""
    from src.services.supabase_client import get_supabase_client

    client = get_supabase_client()
    result = (
        client.table("summary_reports_ML_REIT")
        .select("*")
        .eq("id", report_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Report not found")

    r = result.data[0]
    rj = r.get("report_json") or {}
    return {
        "id": r["id"],
        "company_id": r["company_id"],
        "ticker": rj.get("ticker", ""),
        "company_name": rj.get("company_name", ""),
        "report_type": r["report_type"],
        "period_label": r["period_label"],
        "period_start": r.get("period_start"),
        "period_end": r.get("period_end"),
        "model_used": r.get("model_used"),
        "tokens_used": r.get("tokens_used"),
        "email_sent": r.get("email_sent", False),
        "created_at": r.get("created_at"),
        "report_json": rj,
    }


# ---------------------------------------------------------------------------
# 5. GET /api/extractions
# ---------------------------------------------------------------------------

@api_router.get("/extractions", dependencies=[Depends(require_api_key)])
async def list_extractions(
    company: str | None = Query(None, description="Ticker filter"),
    limit: int = Query(20, ge=1, le=100),
):
    """Recent extractions from the universal pipeline."""
    from src.models.database import get_company_by_ticker
    from src.services.supabase_client import get_supabase_client

    client = get_supabase_client()
    query = (
        client.table("universal_extractions_ML_REIT")
        .select("id, company_id, document_id, document_type, fiscal_year, fiscal_quarter, period_end, extraction_confidence, created_at")
        .order("created_at", desc=True)
        .limit(limit)
    )

    if company:
        co = get_company_by_ticker(company)
        if not co:
            raise HTTPException(status_code=404, detail=f"Company {company.upper()} not found")
        query = query.eq("company_id", co["id"])

    result = query.execute()
    return result.data


# ---------------------------------------------------------------------------
# 6. GET /api/status
# ---------------------------------------------------------------------------

@api_router.get("/status", dependencies=[Depends(require_api_key)])
async def pipeline_status():
    """Pipeline health: last scrape, pending docs, error counts."""
    from src.services.supabase_client import get_supabase_client

    client = get_supabase_client()

    # Last poll per company
    last_polls = (
        client.table("poll_log_ML_REIT")
        .select("company_id, poll_type, completed_at, new_filings_found, error_message")
        .order("completed_at", desc=True)
        .limit(20)
        .execute()
    ).data

    # Pending documents (status not completed/failed)
    pending = (
        client.table("company_documents_ML_REIT")
        .select("id, company_id, document_type, status, created_at")
        .not_.is_("status", "null")
        .in_("status", ["downloaded", "extracting"])
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    ).data

    # Recent errors — filings
    filing_errors = (
        client.table("filings_ML_REIT")
        .select("id, company_id, filing_type, period_label, status, error_message, updated_at")
        .in_("status", ["extraction_failed", "validation_failed"])
        .order("updated_at", desc=True)
        .limit(10)
        .execute()
    ).data

    # Recent errors — documents
    doc_errors = (
        client.table("company_documents_ML_REIT")
        .select("id, company_id, document_type, status, created_at")
        .eq("status", "failed")
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    ).data

    # Company map for tickers
    companies = client.table("companies_ML_REIT").select("id, ticker").execute().data
    co_map = {co["id"]: co["ticker"] for co in companies}

    def _enrich(rows):
        for r in rows:
            r["ticker"] = co_map.get(r.get("company_id"), "?")
        return rows

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "last_polls": _enrich(last_polls),
        "pending_documents": _enrich(pending),
        "recent_filing_errors": _enrich(filing_errors),
        "recent_document_errors": _enrich(doc_errors),
        "error_count": len(filing_errors) + len(doc_errors),
    }


# ---------------------------------------------------------------------------
# 7. GET /api/filings/recent — recent filings for review page
# ---------------------------------------------------------------------------

@api_router.get("/filings/recent", dependencies=[Depends(require_api_key)])
async def recent_filings(
    days: int = Query(30, ge=1, le=90),
):
    """Return filings from the last N days, enriched with company ticker."""
    from datetime import timedelta
    from src.services.supabase_client import get_supabase_client

    client = get_supabase_client()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    result = (
        client.table("filings_ML_REIT")
        .select("id, company_id, filing_type, status, source_url, filing_date, period_label, created_at")
        .gte("created_at", since)
        .neq("status", "skipped")
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )

    # Enrich with ticker
    companies = client.table("companies_ML_REIT").select("id, ticker").execute().data
    co_map = {co["id"]: co["ticker"] for co in companies}

    return [
        {
            **row,
            "ticker": co_map.get(row["company_id"], "?"),
            "detected_at": row["created_at"],
        }
        for row in result.data
    ]


# ---------------------------------------------------------------------------
# 8. POST /api/reports/generate — on-demand report generation
# ---------------------------------------------------------------------------

class GenerateReportRequest(BaseModel):
    ticker: str
    report_type: str  # "monthly" | "quarterly" | "annual"
    year: int
    month: int | None = None
    quarter: int | None = None


@api_router.post("/reports/generate", dependencies=[Depends(require_api_key)])
async def generate_report(request: GenerateReportRequest):
    """Generate a summary report on demand (human-in-the-loop workflow)."""
    from src.models.database import get_company_by_ticker
    from src.services.summary_service import (
        generate_monthly_summary,
        generate_quarterly_summary,
        generate_annual_summary,
    )

    co = get_company_by_ticker(request.ticker)
    if not co:
        raise HTTPException(status_code=404, detail=f"Company {request.ticker.upper()} not found")

    try:
        if request.report_type == "monthly":
            if request.month is None:
                raise HTTPException(status_code=400, detail="month is required for monthly reports")
            result = await generate_monthly_summary(
                company_id=co["id"],
                company_name=co["name"],
                ticker=co["ticker"],
                year=request.year,
                month=request.month,
            )
        elif request.report_type == "quarterly":
            if request.quarter is None:
                raise HTTPException(status_code=400, detail="quarter is required for quarterly reports")
            result = await generate_quarterly_summary(
                company_id=co["id"],
                company_name=co["name"],
                ticker=co["ticker"],
                year=request.year,
                quarter=request.quarter,
            )
        elif request.report_type == "annual":
            result = await generate_annual_summary(
                company_id=co["id"],
                company_name=co["name"],
                ticker=co["ticker"],
                year=request.year,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Invalid report_type: {request.report_type}")

        return {"status": "ok", "report": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate report: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
