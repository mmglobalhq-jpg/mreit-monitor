"""
Summary trigger logic — determines when to generate a summary report
after a new document is processed.

Different companies require different trigger conditions:
- ARR: monthly after monthly_update, quarterly after earnings
- BMNM: quarterly after earnings
- CIM: quarterly after ALL 3 docs (earnings + supplement + presentation)
- AGNC: quarterly after earnings, optional monthly after BV estimate
- NLY: quarterly after ALL 3 docs (earnings + supplement + presentation)
- DX: quarterly after earnings + presentation
"""

import logging
from datetime import date

from src.services.supabase_client import get_supabase_client

logger = logging.getLogger("mreit-monitor.summary_trigger")

# Companies that need multiple documents before triggering a quarterly summary
_COMPLETENESS_CHECK = {
    "CIM": ["quarterly_earnings", "financial_supplement", "investor_presentation"],
    "NLY": ["quarterly_earnings", "financial_supplement", "investor_presentation"],
    "DX": ["quarterly_earnings", "investor_presentation"],
}


def should_generate_summary(
    ticker: str,
    document_type: str,
    company_id: str | None = None,
    fiscal_quarter: int | None = None,
    fiscal_year: int | None = None,
) -> tuple[bool, str]:
    """
    Determine whether a summary should be generated after processing a document.

    Returns:
        Tuple of (should_generate: bool, summary_type: str)
        summary_type is "monthly", "quarterly", or "" if no summary needed
    """
    ticker = ticker.upper()

    # ARR monthly summary after monthly update
    if ticker == "ARR" and document_type == "monthly_update":
        return True, "monthly"

    # ARR quarterly summary after earnings
    if ticker == "ARR" and document_type in ("quarterly_earnings", "earnings_release"):
        return True, "quarterly"

    # BMNM: quarterly after earnings (simple — only has earnings)
    if ticker == "BMNM" and document_type in ("quarterly_earnings", "earnings_release"):
        return True, "quarterly"

    # AGNC: quarterly after earnings, optional monthly after BV estimate
    if ticker == "AGNC":
        if document_type in ("quarterly_earnings", "earnings_release"):
            return True, "quarterly"
        if document_type in ("monthly_book_value", "press_release"):
            return False, ""  # Optional lightweight — not auto-triggered

    # CIM, NLY, DX: completeness check
    if ticker in _COMPLETENESS_CHECK:
        required_types = _COMPLETENESS_CHECK[ticker]

        if document_type not in required_types:
            return False, ""

        # Check if all required documents for this quarter are present
        if company_id and fiscal_quarter and fiscal_year:
            if _check_quarter_complete(company_id, fiscal_quarter, fiscal_year, required_types):
                return True, "quarterly"
            else:
                logger.info(
                    "%s: %s processed but waiting for remaining quarterly docs (Q%d %d)",
                    ticker, document_type, fiscal_quarter, fiscal_year,
                )
                return False, ""
        else:
            # Can't check completeness without fiscal info — don't auto-trigger
            return False, ""

    # Default: don't generate
    return False, ""


def _check_quarter_complete(
    company_id: str,
    fiscal_quarter: int,
    fiscal_year: int,
    required_types: list[str],
) -> bool:
    """Check if all required document types for a quarter are in the documents table."""
    client = get_supabase_client()

    result = (
        client.table("reit_company_documents")
        .select("document_type")
        .eq("company_id", company_id)
        .eq("fiscal_quarter", fiscal_quarter)
        .eq("fiscal_year", fiscal_year)
        .in_("status", ["extracted", "completed"])
        .execute()
    )

    found_types = {r["document_type"] for r in result.data}

    for req in required_types:
        if req not in found_types:
            return False

    return True
