"""
Process an SEC filing (10-K/10-Q) through the universal extraction pipeline.

Reusable for any mREIT. Downloads the HTML/PDF from SEC, extracts structured
data via Claude, and stores in Supabase (company_documents + universal_extractions).

IMPORTANT: The universal_document_processor auto-sets fiscal_year/quarter from
document_date. This script corrects them after processing since the filing date
differs from the period covered (e.g., 10-K filed 2026-02-25 covers FY2025).

Usage:
    # Process a specific preset:
    python -m scripts.process_sec_filing --ticker DX --preset 10k-fy2025

    # Process all presets for a ticker:
    python -m scripts.process_sec_filing --ticker DX --all-presets

    # Custom URL:
    python -m scripts.process_sec_filing --ticker DX --url <URL> \\
        --period-end 2025-12-31 --fiscal-year 2025 --fiscal-quarter 4 \\
        --title "DX FY 2025 10-K"

Adding a new company:
    1. Find 10-K and 10-Q URLs from EDGAR:
       curl -sA "mREIT-Monitor user@email.com" \\
         "https://data.sec.gov/submissions/CIK{cik_padded}.json" | python -m json.tool
    2. Add presets to the PRESETS dict below
    3. Run: python -m scripts.process_sec_filing --ticker XXXX --all-presets
    4. Verify in Supabase: check universal_extractions for extracted metrics
    5. Generate report: POST /api/reports/generate
"""

import asyncio
import argparse
import logging
import sys
from datetime import date

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("process_sec_filing")

# ──────────────────────────────────────────────────────────────────────
# PRESETS — add new companies here for uniform processing
# ──────────────────────────────────────────────────────────────────────

PRESETS = {
    "DX": {
        "10k-fy2025": {
            "url": "https://www.sec.gov/Archives/edgar/data/826675/000082667526000017/dx-20251231.htm",
            "doc_type": "sec_filing",
            "period_end": "2025-12-31",
            "fiscal_year": 2025,
            "fiscal_quarter": 4,
            "title": "DX FY 2025 10-K",
            "filing_date": "2026-02-25",
        },
        "10q-q3-2025": {
            "url": "https://www.sec.gov/Archives/edgar/data/826675/000082667525000153/dx-20250930.htm",
            "doc_type": "sec_filing",
            "period_end": "2025-09-30",
            "fiscal_year": 2025,
            "fiscal_quarter": 3,
            "title": "DX Q3 2025 10-Q",
            "filing_date": "2025-10-27",
        },
    },
    "AGNC": {
        "q3-earnings-2025": {
            "url": "https://www.sec.gov/Archives/edgar/data/1423689/000142368925000101/agnc8kexhibit99193025.htm",
            "doc_type": "quarterly_earnings",
            "period_end": "2025-09-30",
            "fiscal_year": 2025,
            "fiscal_quarter": 3,
            "title": "AGNC Q3 2025 Earnings Release",
            "filing_date": "2025-10-20",
        },
        "10k-fy2025": {
            "url": "https://www.sec.gov/Archives/edgar/data/1423689/000142368926000043/agnc-20251231.htm",
            "doc_type": "sec_filing",
            "period_end": "2025-12-31",
            "fiscal_year": 2025,
            "fiscal_quarter": 4,
            "title": "AGNC FY 2025 10-K",
            "filing_date": "2026-02-23",
        },
        "10q-q3-2025": {
            "url": "https://www.sec.gov/Archives/edgar/data/1423689/000142368925000106/agnc-20250930.htm",
            "doc_type": "sec_filing",
            "period_end": "2025-09-30",
            "fiscal_year": 2025,
            "fiscal_quarter": 3,
            "title": "AGNC Q3 2025 10-Q",
            "filing_date": "2025-10-31",
        },
    },
    "NLY": {
        "q3-fin-supp-2025": {
            "url": "https://www.sec.gov/Archives/edgar/data/1043219/000104321925000008/a2025q3finsupp991.htm",
            "doc_type": "financial_supplement",
            "period_end": "2025-09-30",
            "fiscal_year": 2025,
            "fiscal_quarter": 3,
            "title": "NLY Q3 2025 Financial Supplement",
            "filing_date": "2025-10-22",
        },
        "10k-fy2025": {
            "url": "https://www.sec.gov/Archives/edgar/data/1043219/000104321926000013/nly-20251231.htm",
            "doc_type": "sec_filing",
            "period_end": "2025-12-31",
            "fiscal_year": 2025,
            "fiscal_quarter": 4,
            "title": "NLY FY 2025 10-K",
            "filing_date": "2026-02-12",
        },
        "10q-q3-2025": {
            "url": "https://www.sec.gov/Archives/edgar/data/1043219/000104321925000012/nly-20250930.htm",
            "doc_type": "sec_filing",
            "period_end": "2025-09-30",
            "fiscal_year": 2025,
            "fiscal_quarter": 3,
            "title": "NLY Q3 2025 10-Q",
            "filing_date": "2025-10-30",
        },
    },
    "ORC": {
        "q3-earnings-2025": {
            "url": "https://www.sec.gov/Archives/edgar/data/1518621/000143774925031058/ex_869604.htm",
            "doc_type": "quarterly_earnings",
            "period_end": "2025-09-30",
            "fiscal_year": 2025,
            "fiscal_quarter": 3,
            "title": "ORC Q3 2025 Earnings Release",
            "filing_date": "2025-10-15",
        },
        "10k-fy2025": {
            "url": "https://www.sec.gov/Archives/edgar/data/1518621/000143774926004889/orc20251231_10k.htm",
            "doc_type": "sec_filing",
            "period_end": "2025-12-31",
            "fiscal_year": 2025,
            "fiscal_quarter": 4,
            "title": "ORC FY 2025 10-K",
            "filing_date": "2026-02-20",
        },
        "10q-q3-2025": {
            "url": "https://www.sec.gov/Archives/edgar/data/1518621/000143774925031728/orc20250930_10q.htm",
            "doc_type": "sec_filing",
            "period_end": "2025-09-30",
            "fiscal_year": 2025,
            "fiscal_quarter": 3,
            "title": "ORC Q3 2025 10-Q",
            "filing_date": "2025-10-24",
        },
    },
}


async def process_filing(
    ticker: str,
    url: str,
    doc_type: str,
    period_end: str,
    fiscal_year: int,
    fiscal_quarter: int,
    title: str,
    filing_date: str | None = None,
):
    """Download, extract, and store a single SEC filing with correct metadata."""
    from src.config.company_registry import get_company_config
    from src.models.database import get_company_by_ticker
    from src.parsers.universal_document_processor import process_document
    from src.services.supabase_client import get_supabase_client

    company = get_company_by_ticker(ticker)
    if not company:
        logger.error("Company %s not found in database", ticker)
        return False

    config = get_company_config(ticker)
    if not config:
        logger.error("No config for %s in company_registry", ticker)
        return False

    logger.info("=" * 70)
    logger.info("Processing %s: %s", ticker, title)
    logger.info("URL: %s", url)
    logger.info("Period: %s (FY%d Q%d)", period_end, fiscal_year, fiscal_quarter)
    logger.info("=" * 70)

    doc_date = date.fromisoformat(filing_date) if filing_date else date.today()

    success = await process_document(
        company_id=company["id"],
        company_name=company["name"],
        ticker=ticker,
        company_config=config,
        source_url=url,
        document_type=doc_type,
        document_date=doc_date,
        period_label=title,
        title=title,
        skip_email=True,
    )

    if not success:
        logger.error("FAILED — %s extraction failed", title)
        return False

    # Fix metadata — process_document auto-sets fiscal_year/quarter from filing_date,
    # which is wrong for 10-K/10-Q (filing date ≠ period covered)
    client = get_supabase_client()

    # Fix company_documents record
    doc_result = (
        client.table("company_documents_ML_REIT")
        .update({
            "fiscal_year": fiscal_year,
            "fiscal_quarter": fiscal_quarter,
            "period_end": period_end,
        })
        .eq("company_id", company["id"])
        .eq("source_url", url)
        .execute()
    )
    doc_id = doc_result.data[0]["id"] if doc_result.data else None

    # Fix universal_extractions record
    if doc_id:
        client.table("universal_extractions_ML_REIT").update({
            "period_end": period_end,
            "fiscal_year": fiscal_year,
            "fiscal_quarter": fiscal_quarter,
        }).eq("document_id", doc_id).execute()

    logger.info("SUCCESS — %s extracted, metadata corrected (period=%s)", title, period_end)

    # Verify extraction
    if doc_id:
        ext = (
            client.table("universal_extractions_ML_REIT")
            .select("extraction_confidence,book_value_per_share,portfolio_size,leverage_ratio,agency_rmbs_holdings")
            .eq("document_id", doc_id)
            .execute()
        )
        if ext.data:
            e = ext.data[0]
            logger.info("  Confidence: %.2f", e.get("extraction_confidence", 0))
            logger.info("  Book value: %s", e.get("book_value_per_share"))
            logger.info("  Portfolio: %s", e.get("portfolio_size"))
            logger.info("  RMBS: %s", e.get("agency_rmbs_holdings"))
            logger.info("  Leverage: %s", e.get("leverage_ratio"))

    return True


async def main():
    parser = argparse.ArgumentParser(description="Process SEC filings for mREITs")
    parser.add_argument("--ticker", required=True, help="Company ticker (e.g., DX, AGNC)")
    parser.add_argument("--preset", help="Use a preset config (e.g., 10k-fy2025)")
    parser.add_argument("--all-presets", action="store_true", help="Run all presets for ticker")
    parser.add_argument("--url", help="SEC filing URL (for custom processing)")
    parser.add_argument("--doc-type", default="sec_filing")
    parser.add_argument("--period-end", help="Period end date (YYYY-MM-DD)")
    parser.add_argument("--fiscal-year", type=int)
    parser.add_argument("--fiscal-quarter", type=int)
    parser.add_argument("--title", help="Filing title")
    parser.add_argument("--filing-date", help="Filing date (YYYY-MM-DD)")
    args = parser.parse_args()

    ticker = args.ticker.upper()

    if args.all_presets:
        presets = PRESETS.get(ticker, {})
        if not presets:
            logger.error("No presets for %s. Available tickers: %s", ticker, list(PRESETS.keys()))
            sys.exit(1)
        results = {}
        for name, cfg in presets.items():
            try:
                ok = await process_filing(ticker=ticker, **cfg)
                results[name] = ok
            except Exception as e:
                logger.error("FAILED %s: %s", name, e, exc_info=True)
                results[name] = False

        print(f"\n{'=' * 50}")
        print(f"  {ticker} SEC Filing Processing Results")
        print(f"{'=' * 50}")
        for name, ok in results.items():
            print(f"  {name:20s} {'OK' if ok else 'FAILED'}")
        return

    if args.preset:
        presets = PRESETS.get(ticker, {})
        cfg = presets.get(args.preset)
        if not cfg:
            available = list(presets.keys()) if presets else f"(no presets for {ticker})"
            logger.error("Preset '%s' not found. Available: %s", args.preset, available)
            sys.exit(1)
        await process_filing(ticker=ticker, **cfg)
        return

    if not all([args.url, args.period_end, args.fiscal_year, args.fiscal_quarter, args.title]):
        parser.error("Need --preset or all of: --url, --period-end, --fiscal-year, --fiscal-quarter, --title")

    await process_filing(
        ticker=ticker,
        url=args.url,
        doc_type=args.doc_type,
        period_end=args.period_end,
        fiscal_year=args.fiscal_year,
        fiscal_quarter=args.fiscal_quarter,
        title=args.title,
        filing_date=args.filing_date,
    )


if __name__ == "__main__":
    asyncio.run(main())
