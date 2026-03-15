"""
Earnings release parser — orchestrates the full processing pipeline
for a single quarterly earnings press release (HTML page).

Pipeline:
1. Create filing record in Supabase
2. Download HTML press release
3. Upload raw HTML to Supabase Storage
4. Extract clean text from HTML (BeautifulSoup)
5. Send to Claude for structured extraction
6. Validate and store in quarterly_metrics table
7. Run quarterly comparison agent
8. Send email alert
9. Update filing status to completed
"""

import json
import logging
from datetime import date, datetime

from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from src.models.schemas import (
    FilingStatus,
    FilingType,
    QuarterlyEarningsExtraction,
)
from src.parsers.utils import get_nested as _get_nested, parse_date_string as _parse_date_string
from src.services.supabase_client import get_supabase_client

logger = logging.getLogger("mreit-monitor.earnings_parser")


async def process_earnings_release(
    company_id: str,
    company_name: str,
    ticker: str,
    source_url: str,
    filing_date: date,
    period_label: str,  # e.g., "Q4 2025"
) -> bool:
    """
    Full pipeline for processing a single quarterly earnings press release.

    Returns True if processing completed successfully.
    """
    from src.agents.comparison_agent import generate_monthly_comparison
    from src.agents.extraction_agent import extract_quarterly_earnings
    from src.services.downloader import (
        build_storage_path,
        download_html,
        upload_to_storage,
    )
    from src.services.email_service import send_filing_alert

    client = get_supabase_client()
    filing_id = None

    try:
        # ============================================================
        # Step 1: Create filing record
        # ============================================================
        filing_record = {
            "company_id": company_id,
            "filing_type": FilingType.EARNINGS_RELEASE.value,
            "status": FilingStatus.DETECTED.value,
            "source_url": source_url,
            "source_page": "quarterly_reports",
            "filing_date": filing_date.isoformat(),
            "period_label": period_label,
        }
        result = client.table("filings").insert(filing_record).execute()
        filing_id = result.data[0]["id"]
        logger.info(
            "Created filing record %s for %s %s earnings release",
            filing_id,
            ticker,
            period_label,
        )

        # ============================================================
        # Step 2: Download HTML
        # ============================================================
        html_content = await download_html(source_url)

        # ============================================================
        # Step 3: Upload raw HTML to Supabase Storage
        # ============================================================
        storage_path = build_storage_path(ticker, "earnings_release", period_label)
        html_bytes = html_content.encode("utf-8")
        await upload_to_storage(
            html_bytes,
            storage_path,
            content_type="text/html",
        )

        client.table("filings").update(
            {
                "status": FilingStatus.DOWNLOADED.value,
                "storage_path": storage_path,
                "downloaded_at": datetime.utcnow().isoformat(),
            }
        ).eq("id", filing_id).execute()

        # ============================================================
        # Step 4: Extract clean text from HTML
        # ============================================================
        clean_text = _extract_text_from_html(html_content)
        logger.info(
            "Extracted %d characters of text from earnings release HTML",
            len(clean_text),
        )

        # ============================================================
        # Step 5: Send to Claude for structured extraction
        # ============================================================
        client.table("filings").update(
            {
                "status": FilingStatus.EXTRACTING.value,
            }
        ).eq("id", filing_id).execute()

        extraction, extraction_meta = await extract_quarterly_earnings(clean_text)

        client.table("filings").update(
            {
                "status": FilingStatus.EXTRACTED.value,
                "extraction_model": extraction_meta["model"],
                "extraction_tokens_used": (
                    extraction_meta["input_tokens"]
                    + extraction_meta["output_tokens"]
                ),
                "raw_extraction_json": json.loads(extraction_meta["raw_response"]),
                "extracted_at": datetime.utcnow().isoformat(),
            }
        ).eq("id", filing_id).execute()

        # ============================================================
        # Step 6: Store structured data in quarterly_metrics table
        # ============================================================
        await _store_quarterly_data(client, filing_id, company_id, extraction)

        logger.info(
            "Stored quarterly metrics for %s %s", ticker, period_label
        )

        # ============================================================
        # Step 7: Run quarterly comparison agent
        # ============================================================
        client.table("filings").update(
            {
                "status": FilingStatus.COMPARING.value,
            }
        ).eq("id", filing_id).execute()

        prior_data = _get_prior_quarterly_data(
            client, company_id, extraction.period_end_date
        )

        analysis = None
        if prior_data:
            current_data = extraction.model_dump()
            analysis, comparison_meta = await generate_monthly_comparison(
                company_name=company_name,
                ticker=ticker,
                current_period=period_label,
                prior_period=prior_data["period_label"],
                current_data=current_data,
                prior_data=prior_data["data"],
            )

            # Store analysis
            client.table("agent_analyses").insert(
                {
                    "filing_id": filing_id,
                    "company_id": company_id,
                    "analysis_type": "quarterly_comparison",
                    "period_label": (
                        f"{period_label} vs {prior_data['period_label']}"
                    ),
                    "summary": analysis.summary,
                    "full_analysis": analysis.full_analysis,
                    "key_changes": [
                        c.model_dump() for c in analysis.key_metric_changes
                    ],
                    "anomalies": [
                        a.model_dump() for a in analysis.anomalies
                    ],
                    "current_period_date": extraction.period_end_date,
                    "prior_period_date": prior_data["period_end_date"],
                    "model_used": comparison_meta["model"],
                    "tokens_used": (
                        comparison_meta["input_tokens"]
                        + comparison_meta["output_tokens"]
                    ),
                }
            ).execute()

            logger.info(
                "Quarterly comparison analysis stored for %s %s",
                ticker,
                period_label,
            )
        else:
            logger.info(
                "No prior quarter data for comparison — skipping comparison agent"
            )

        # ============================================================
        # Step 8: Send email alert
        # ============================================================
        metrics_summary = _build_quarterly_metrics_summary(
            extraction, prior_data
        )

        await send_filing_alert(
            ticker=ticker,
            company_name=company_name,
            filing_type_label="Quarterly Earnings Release",
            period_label=period_label,
            source_url=source_url,
            analysis=analysis,
            metrics_summary=metrics_summary,
        )

        # ============================================================
        # Step 9: Mark complete
        # ============================================================
        client.table("filings").update(
            {
                "status": FilingStatus.COMPLETED.value,
                "completed_at": datetime.utcnow().isoformat(),
            }
        ).eq("id", filing_id).execute()

        logger.info(
            "Successfully processed %s %s earnings release",
            ticker,
            period_label,
        )
        return True

    except Exception as e:
        logger.error(
            "Failed to process %s %s earnings release: %s",
            ticker,
            period_label,
            str(e),
        )
        if filing_id:
            client.table("filings").update(
                {
                    "status": FilingStatus.EXTRACTION_FAILED.value,
                    "error_message": str(e)[:1000],
                }
            ).eq("id", filing_id).execute()
        raise


def _extract_text_from_html(html_content: str) -> str:
    """
    Extract clean readable text from an earnings release HTML page.

    Strips all tags, collapses whitespace, and preserves table structure
    by inserting separators between table cells.
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove script and style elements
    for element in soup(["script", "style", "meta", "link", "noscript"]):
        element.decompose()

    # Insert separators for table cell boundaries so numbers stay distinguishable
    for td in soup.find_all(["td", "th"]):
        td.insert_before(" | ")
    for tr in soup.find_all("tr"):
        tr.insert_after("\n")

    # Get text with newlines preserved for block elements
    text = soup.get_text(separator="\n")

    # Clean up excessive whitespace while preserving paragraph breaks
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            lines.append(stripped)

    return "\n".join(lines)


async def _store_quarterly_data(
    client,
    filing_id: str,
    company_id: str,
    extraction: QuarterlyEarningsExtraction,
) -> None:
    """
    Map the QuarterlyEarningsExtraction fields to the quarterly_metrics table
    columns and upsert the record.

    Upserts on (company_id, period_end_date) to handle reprocessing.
    """
    period_end_date = _parse_date_string(extraction.period_end_date)
    if not period_end_date:
        # Fall back to raw string if parsing fails
        period_end_date = extraction.period_end_date

    metrics = {
        "filing_id": filing_id,
        "company_id": company_id,
        "period_end_date": period_end_date,
        "quarter_label": extraction.quarter_label,
        # Income Statement
        "gaap_net_income_millions": extraction.gaap_net_income_millions,
        "gaap_eps": extraction.gaap_eps,
        "net_interest_income_millions": extraction.net_interest_income_millions,
        "distributable_earnings_millions": extraction.distributable_earnings_millions,
        "distributable_eps": extraction.distributable_eps,
        # Yield & Spread
        "avg_interest_income_rate": extraction.avg_interest_income_rate,
        "avg_interest_expense_rate": extraction.avg_interest_expense_rate,
        "economic_interest_income_rate": extraction.economic_interest_income_rate,
        "economic_interest_expense_rate": extraction.economic_interest_expense_rate,
        "economic_net_interest_spread": extraction.economic_net_interest_spread,
        # Balance Sheet
        "book_value_per_share": extraction.book_value_per_share,
        "total_portfolio_billions": extraction.total_portfolio_billions,
        "agency_mbs_pct": extraction.agency_mbs_pct,
        # Returns
        "quarterly_total_economic_return": extraction.quarterly_total_economic_return,
        "ytd_total_economic_return": extraction.ytd_total_economic_return,
        "annual_total_economic_return": extraction.annual_total_economic_return,
        # Capital & Leverage
        "liquidity_millions": extraction.liquidity_millions,
        "repo_agreements_net_millions": extraction.repo_agreements_net_millions,
        "affiliate_repo_pct": extraction.affiliate_repo_pct,
        "debt_equity_ratio": extraction.debt_equity_ratio,
        "implied_leverage": extraction.implied_leverage,
        # Equity Issuance
        "atm_capital_raised_millions": extraction.atm_capital_raised_millions,
        "atm_shares_issued": extraction.atm_shares_issued,
        # Dividends
        "quarterly_dividend_per_share": extraction.quarterly_dividend_per_share,
        # Tax Treatment
        "ordinary_income_pct": extraction.ordinary_income_pct,
        "return_of_capital_pct": extraction.return_of_capital_pct,
    }

    # Remove None values to let database defaults apply
    metrics = {k: v for k, v in metrics.items() if v is not None}

    client.table("quarterly_metrics").upsert(
        metrics, on_conflict="company_id,period_end_date"
    ).execute()


def _get_prior_quarterly_data(
    client, company_id: str, current_period_end: str
) -> dict | None:
    """
    Get the prior quarter's data for comparison.

    Looks up the most recent quarterly_metrics row before the current
    period_end_date.
    """
    # Parse the current period end date for comparison
    parsed_date = _parse_date_string(current_period_end)
    if not parsed_date:
        parsed_date = current_period_end

    result = (
        client.table("quarterly_metrics")
        .select("*")
        .eq("company_id", company_id)
        .lt("period_end_date", parsed_date)
        .order("period_end_date", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    prior_metrics = result.data[0]
    prior_filing_id = prior_metrics["filing_id"]
    prior_period_end = prior_metrics["period_end_date"]

    # Get the raw extraction JSON from the filings table for richer comparison
    filing_result = (
        client.table("filings")
        .select("raw_extraction_json, period_label")
        .eq("id", prior_filing_id)
        .limit(1)
        .execute()
    )

    if filing_result.data and filing_result.data[0].get("raw_extraction_json"):
        return {
            "period_end_date": prior_period_end,
            "period_label": filing_result.data[0]["period_label"],
            "data": filing_result.data[0]["raw_extraction_json"],
        }

    # Fall back to the quarterly_metrics row itself if no raw extraction
    return {
        "period_end_date": prior_period_end,
        "period_label": prior_metrics.get("quarter_label", "Prior Quarter"),
        "data": prior_metrics,
    }


def _build_quarterly_metrics_summary(
    extraction: QuarterlyEarningsExtraction,
    prior_data: dict | None,
) -> list[dict]:
    """Build a summary of key quarterly metrics with deltas for the email alert."""
    metrics = [
        ("GAAP EPS", extraction.gaap_eps, "$", "gaap_eps"),
        ("Distributable EPS", extraction.distributable_eps, "$", "distributable_eps"),
        ("Book Value/Share", extraction.book_value_per_share, "$", "book_value_per_share"),
        ("Net Interest Income ($M)", extraction.net_interest_income_millions, "", "net_interest_income_millions"),
        ("Econ. Net Interest Spread", extraction.economic_net_interest_spread, "%", "economic_net_interest_spread"),
        ("Quarterly Total Econ. Return", extraction.quarterly_total_economic_return, "%", "quarterly_total_economic_return"),
        ("Debt/Equity", extraction.debt_equity_ratio, "x", "debt_equity_ratio"),
        ("Implied Leverage", extraction.implied_leverage, "x", "implied_leverage"),
        ("Liquidity ($M)", extraction.liquidity_millions, "", "liquidity_millions"),
        ("Quarterly Dividend/Share", extraction.quarterly_dividend_per_share, "$", "quarterly_dividend_per_share"),
    ]

    prior = prior_data["data"] if prior_data else None

    summary = []
    for name, current_val, suffix, key in metrics:
        entry = {"name": name}

        # Format current value
        if current_val is not None:
            if suffix == "$":
                entry["current"] = f"${current_val}"
            else:
                entry["current"] = f"{current_val}{suffix}"
        else:
            entry["current"] = "\u2014"

        # Look up prior value — try direct key first (quarterly_metrics row),
        # then nested path (raw extraction JSON)
        prior_val = None
        if prior:
            prior_val = prior.get(key)
            if prior_val is None:
                prior_val = _get_nested(prior, key)

        if prior_val is not None:
            if suffix == "$":
                entry["prior"] = f"${prior_val}"
            else:
                entry["prior"] = f"{prior_val}{suffix}"

            if current_val is not None:
                try:
                    delta = float(current_val) - float(prior_val)
                except (TypeError, ValueError):
                    delta = None

                if delta is not None:
                    if suffix == "$":
                        entry["delta_str"] = f"{'+' if delta >= 0 else ''}${delta:.2f}"
                    elif suffix == "x":
                        entry["delta_str"] = f"{'+' if delta >= 0 else ''}{delta:.1f}x"
                    elif suffix == "%":
                        entry["delta_str"] = f"{'+' if delta >= 0 else ''}{delta:.1f}pp"
                    else:
                        entry["delta_str"] = f"{'+' if delta >= 0 else ''}{delta:.1f}"

                    if abs(delta) < 0.001:
                        entry["direction"] = "flat"
                    elif delta > 0:
                        entry["direction"] = "up"
                    else:
                        entry["direction"] = "down"
                else:
                    entry["delta_str"] = "\u2014"
                    entry["direction"] = "flat"
            else:
                entry["delta_str"] = "\u2014"
                entry["direction"] = "flat"
        else:
            entry["prior"] = "\u2014"
            entry["delta_str"] = "\u2014"
            entry["direction"] = "flat"

        summary.append(entry)

    return summary


