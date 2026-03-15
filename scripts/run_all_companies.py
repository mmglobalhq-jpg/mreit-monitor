"""
Extract Q4 2025 data for all new companies and generate summary reports.
ARR already has a March 2026 monthly summary.
"""
import asyncio
import logging
import sys
from datetime import date

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("run_all")

# Test documents for each new company (Q4 2025)
NEW_COMPANY_DOCS = {
    "BMNM": {
        "url": "https://www.globenewswire.com/news-release/2026/03/12/3255123/24159/en/Bimini-Capital-Management-Announces-Fourth-Quarter-and-Full-Year-2025-Results-and-Share-Repurchase-Plan.html",
        "doc_type": "quarterly_earnings",
        "title": "BMNM Q4 2025 Earnings Release",
        "period_label": "Q4 2025",
        "document_date": date(2026, 3, 12),
    },
    "CIM": {
        "url": "https://www.sec.gov/Archives/edgar/data/0001409493/000140949326000007/pressrelease-q42025.htm",
        "doc_type": "quarterly_earnings",
        "title": "CIM Q4 2025 Earnings Press Release",
        "period_label": "Q4 2025",
        "document_date": date(2026, 2, 13),
    },
    "AGNC": {
        "url": "https://www.sec.gov/Archives/edgar/data/0001423689/000142368926000024/agnc8kexhibit991123125.htm",
        "doc_type": "quarterly_earnings",
        "title": "AGNC Q4 2025 Earnings Release",
        "period_label": "Q4 2025",
        "document_date": date(2026, 1, 27),
    },
    "NLY": {
        "url": "https://www.sec.gov/Archives/edgar/data/0001043219/000104321926000008/a2025q4finsupp991.htm",
        "doc_type": "financial_supplement",
        "title": "NLY Q4 2025 Financial Supplement",
        "period_label": "Q4 2025",
        "document_date": date(2026, 1, 29),
    },
    "DX": {
        "url": "https://www.sec.gov/Archives/edgar/data/0000826675/000082667526000004/a4q25earningsrelease.htm",
        "doc_type": "quarterly_earnings",
        "title": "DX Q4 2025 Earnings Release",
        "period_label": "Q4 2025",
        "document_date": date(2026, 2, 5),
    },
}


async def extract_and_summarize(ticker, doc_info):
    """Extract a document and generate a quarterly summary for one company."""
    from src.config.company_registry import get_company_config
    from src.models.database import get_company_by_ticker
    from src.parsers.universal_document_processor import process_document
    from src.services.summary_service import generate_quarterly_summary

    company = get_company_by_ticker(ticker)
    if not company:
        logger.error("%s not found in DB", ticker)
        return False

    config = get_company_config(ticker)
    if not config:
        logger.error("No registry config for %s", ticker)
        return False

    # Step 1: Extract the document
    logger.info("=" * 60)
    logger.info("EXTRACTING %s: %s", ticker, doc_info["title"])
    logger.info("=" * 60)

    success = await process_document(
        company_id=company["id"],
        company_name=company["name"],
        ticker=ticker,
        company_config=config,
        source_url=doc_info["url"],
        document_type=doc_info["doc_type"],
        document_date=doc_info["document_date"],
        period_label=doc_info["period_label"],
        title=doc_info["title"],
    )

    if not success:
        logger.error("Extraction failed for %s", ticker)
        return False

    logger.info("Extraction complete for %s", ticker)

    # Step 2: Generate quarterly summary
    logger.info("Generating Q4 2025 quarterly summary for %s...", ticker)

    try:
        result = await generate_quarterly_summary(
            company_id=company["id"],
            company_name=company["name"],
            ticker=ticker,
            year=2025,
            quarter=4,
        )
        logger.info("Summary generated for %s: %s", ticker, result.get("period_label", "Q4 2025"))
        return True
    except Exception as e:
        logger.error("Summary generation failed for %s: %s", ticker, e)
        return False


async def main():
    results = {}

    # Process each company sequentially to avoid Claude API rate limits
    for ticker, doc_info in NEW_COMPANY_DOCS.items():
        try:
            success = await extract_and_summarize(ticker, doc_info)
            results[ticker] = "OK" if success else "FAILED"
        except Exception as e:
            logger.error("Fatal error for %s: %s", ticker, e, exc_info=True)
            results[ticker] = f"ERROR: {e}"

    # Print summary
    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)
    for ticker, status in results.items():
        print(f"  {ticker:6s}  {status}")
    print()
    print("ARR: Already has March 2026 monthly summary")
    print("Review all reports at: http://localhost:8000/review/")


if __name__ == "__main__":
    asyncio.run(main())
