"""
Frontend API routes — clean JSON endpoints for the Next.js frontend.

All endpoints require X-API-Key header authentication.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import APIKeyHeader

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
        client.table("summary_reports")
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
            client.table("summary_reports")
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
        client.table("summary_reports")
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
        client.table("universal_extractions")
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
        client.table("poll_log")
        .select("company_id, poll_type, completed_at, new_filings_found, error_message")
        .order("completed_at", desc=True)
        .limit(20)
        .execute()
    ).data

    # Pending documents (status not completed/failed)
    pending = (
        client.table("company_documents")
        .select("id, company_id, document_type, status, created_at")
        .not_.is_("status", "null")
        .in_("status", ["downloaded", "extracting"])
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    ).data

    # Recent errors — filings
    filing_errors = (
        client.table("filings")
        .select("id, company_id, filing_type, period_label, status, error_message, updated_at")
        .in_("status", ["extraction_failed", "validation_failed"])
        .order("updated_at", desc=True)
        .limit(10)
        .execute()
    ).data

    # Recent errors — documents
    doc_errors = (
        client.table("company_documents")
        .select("id, company_id, document_type, status, created_at")
        .eq("status", "failed")
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    ).data

    # Company map for tickers
    companies = client.table("companies").select("id, ticker").execute().data
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
