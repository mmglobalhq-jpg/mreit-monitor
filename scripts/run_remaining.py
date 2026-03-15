"""Extract and generate summaries for the 4 remaining companies (CIM, AGNC, NLY, DX)."""
import asyncio
import logging
import sys
from datetime import date

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s", stream=sys.stdout)
logger = logging.getLogger("run_remaining")

REMAINING = {
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


async def process_one(ticker, doc_info):
    from src.config.company_registry import get_company_config
    from src.models.database import get_company_by_ticker
    from src.parsers.universal_document_processor import process_document
    from src.services.summary_service import generate_quarterly_summary

    company = get_company_by_ticker(ticker)
    config = get_company_config(ticker)

    logger.info("=" * 60)
    logger.info("PROCESSING %s: %s", ticker, doc_info["title"])
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
        logger.error("Extraction FAILED for %s", ticker)
        return False

    logger.info("Extraction OK for %s — generating summary...", ticker)

    result = await generate_quarterly_summary(
        company_id=company["id"],
        company_name=company["name"],
        ticker=ticker,
        year=2025,
        quarter=4,
    )
    logger.info("Summary generated for %s", ticker)
    return True


async def main():
    results = {}
    for ticker, doc_info in REMAINING.items():
        try:
            ok = await process_one(ticker, doc_info)
            results[ticker] = "OK" if ok else "FAILED"
        except Exception as e:
            logger.error("Error for %s: %s", ticker, e, exc_info=True)
            results[ticker] = f"ERROR: {e}"

    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)
    for t, s in results.items():
        print(f"  {t:6s}  {s}")

if __name__ == "__main__":
    asyncio.run(main())
