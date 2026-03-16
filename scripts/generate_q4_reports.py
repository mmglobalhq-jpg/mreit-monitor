"""
Generate Q4 2025 quarterly reports for companies that have sufficient data.

Usage:
    python -m scripts.generate_q4_reports                  # all companies
    python -m scripts.generate_q4_reports --ticker BMNM    # single company
"""
import asyncio
import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("generate_q4_reports")

TICKERS = ["BMNM", "CIM", "AGNC", "NLY", "ORC"]


async def generate_report(ticker: str) -> bool:
    from src.models.database import get_company_by_ticker
    from src.services.summary_service import generate_quarterly_summary

    company = get_company_by_ticker(ticker)
    if not company:
        logger.error("%s not found in DB", ticker)
        return False

    logger.info("=" * 60)
    logger.info("Generating Q4 2025 report for %s (%s)", ticker, company["name"])
    logger.info("=" * 60)

    try:
        result = await generate_quarterly_summary(
            company_id=company["id"],
            company_name=company["name"],
            ticker=company["ticker"],
            year=2025,
            quarter=4,
        )
        logger.info("Report generated for %s: %s", ticker, result.get("period_label", "Q4 2025"))
        return True
    except Exception as e:
        logger.error("Report generation failed for %s: %s", ticker, e, exc_info=True)
        return False


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", help="Generate for a single ticker")
    args = parser.parse_args()

    tickers = [args.ticker.upper()] if args.ticker else TICKERS
    results = {}

    for ticker in tickers:
        try:
            ok = await generate_report(ticker)
            results[ticker] = "OK" if ok else "FAILED"
        except Exception as e:
            logger.error("Fatal error for %s: %s", ticker, e, exc_info=True)
            results[ticker] = f"ERROR: {e}"

    print(f"\n{'=' * 60}")
    print("  Q4 2025 Report Generation Results")
    print(f"{'=' * 60}")
    for ticker, status in results.items():
        print(f"  {ticker:6s}  {status}")


if __name__ == "__main__":
    asyncio.run(main())
