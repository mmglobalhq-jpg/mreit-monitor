"""
Database helpers for Supabase table operations.

Provides convenience functions for common queries across
the filings, metrics, and analysis tables.
"""

import logging
from datetime import date

from src.services.supabase_client import get_supabase_client

logger = logging.getLogger("mreit-monitor.database")


def get_company_by_ticker(ticker: str) -> dict | None:
    """Look up a company by ticker symbol."""
    client = get_supabase_client()
    result = client.table("reit_companies").select("*").eq("ticker", ticker.upper()).limit(1).execute()
    return result.data[0] if result.data else None


def get_active_companies() -> list[dict]:
    """Get all active companies."""
    client = get_supabase_client()
    result = client.table("reit_companies").select("*").eq("is_active", True).execute()
    return result.data


def get_latest_filing(company_id: str, filing_type: str | None = None) -> dict | None:
    """Get the most recent filing for a company, optionally filtered by type."""
    client = get_supabase_client()
    query = client.table("reit_filings").select("*").eq("company_id", company_id).order("filing_date", desc=True).limit(1)
    if filing_type:
        query = query.eq("filing_type", filing_type)
    result = query.execute()
    return result.data[0] if result.data else None


def get_latest_monthly_metrics(company_id: str) -> dict | None:
    """Get the most recent monthly metrics for a company."""
    client = get_supabase_client()
    result = (
        client.table("reit_monthly_metrics")
        .select("*")
        .eq("company_id", company_id)
        .order("as_of_date", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def get_monthly_metrics_history(company_id: str, months: int = 12) -> list[dict]:
    """Get the last N months of monthly metrics for a company."""
    client = get_supabase_client()
    result = (
        client.table("reit_monthly_metrics")
        .select("*")
        .eq("company_id", company_id)
        .order("as_of_date", desc=True)
        .limit(months)
        .execute()
    )
    return result.data


def get_portfolio_positions_for_filing(filing_id: str) -> list[dict]:
    """Get all portfolio positions for a specific filing."""
    client = get_supabase_client()
    result = (
        client.table("reit_portfolio_positions")
        .select("*")
        .eq("filing_id", filing_id)
        .execute()
    )
    return result.data


def log_poll(company_id: str, poll_type: str, poll_url: str, new_filings: int = 0, error: str | None = None):
    """Log a polling run to the poll_log table."""
    from datetime import datetime
    client = get_supabase_client()
    client.table("reit_poll_log").insert({
        "company_id": company_id,
        "poll_type": poll_type,
        "poll_url": poll_url,
        "completed_at": datetime.utcnow().isoformat(),
        "new_filings_found": new_filings,
        "error_message": error,
    }).execute()


def filter_new_filings(detected: list, company_id: str) -> list:
    """Filter out filings already in the filings table by source_url."""
    client = get_supabase_client()
    existing = client.table("reit_filings").select("source_url").eq("company_id", company_id).execute()
    existing_urls = {r["source_url"] for r in existing.data}
    return [f for f in detected if f.source_url not in existing_urls]
