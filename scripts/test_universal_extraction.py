"""
Test universal extraction against one document per company.

Uses Q4 2025 documents (URLs from the spec). Downloads each document,
runs the universal extractor, and prints results.

Usage:
    python -m scripts.test_universal_extraction
    python -m scripts.test_universal_extraction --ticker AGNC
"""

import asyncio
import argparse
import logging
import sys

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("test_universal_extraction")

# Q4 2025 test documents — one per company
TEST_DOCUMENTS = {
    "ARR": {
        "url": "https://www.armourreit.com/static-files/c40ff395-3917-41f6-8698-19c87315f4bc",
        "doc_type": "monthly_update",
        "is_pdf": True,
        "description": "March 2026 monthly update PDF",
    },
    "BMNM": {
        "url": "https://www.globenewswire.com/news-release/2026/03/12/3255123/24159/en/Bimini-Capital-Management-Announces-Fourth-Quarter-and-Full-Year-2025-Results-and-Share-Repurchase-Plan.html",
        "doc_type": "quarterly_earnings",
        "is_pdf": False,
        "description": "Q4 2025 earnings release (GlobeNewswire HTML)",
    },
    "CIM": {
        "url": "https://www.sec.gov/Archives/edgar/data/0001409493/000140949326000007/pressrelease-q42025.htm",
        "doc_type": "quarterly_earnings",
        "is_pdf": False,
        "description": "Q4 2025 earnings press release (SEC)",
    },
    "AGNC": {
        "url": "https://www.sec.gov/Archives/edgar/data/0001423689/000142368926000024/agnc8kexhibit991123125.htm",
        "doc_type": "quarterly_earnings",
        "is_pdf": False,
        "description": "Q4 2025 earnings release (SEC exhibit)",
    },
    "NLY": {
        "url": "https://www.sec.gov/Archives/edgar/data/0001043219/000104321926000008/a2025q4finsupp991.htm",
        "doc_type": "financial_supplement",
        "is_pdf": False,
        "description": "Q4 2025 financial supplement (SEC)",
    },
    "DX": {
        "url": "https://www.sec.gov/Archives/edgar/data/0000826675/000082667526000004/a4q25earningsrelease.htm",
        "doc_type": "quarterly_earnings",
        "is_pdf": False,
        "description": "Q4 2025 earnings release (SEC)",
    },
}


async def test_single_company(ticker: str):
    """Download and extract one document for a company."""
    from src.config.company_registry import get_company_config
    from src.agents.universal_extractor import extract_document

    doc_info = TEST_DOCUMENTS.get(ticker)
    if not doc_info:
        logger.error("No test document for %s", ticker)
        return None

    config = get_company_config(ticker)
    if not config:
        logger.error("No company config for %s", ticker)
        return None

    logger.info("=" * 70)
    logger.info("Testing %s: %s", ticker, doc_info["description"])
    logger.info("URL: %s", doc_info["url"])
    logger.info("=" * 70)

    # Download the document
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=60.0,
        headers={"User-Agent": "mREIT-Monitor/1.0 test@example.com"},
    ) as http_client:
        response = await http_client.get(doc_info["url"])
        response.raise_for_status()

    content = response.content if doc_info["is_pdf"] else response.text

    # Run extraction
    extraction, metadata = await extract_document(
        content=content,
        document_type=doc_info["doc_type"],
        company_config=config,
        source_url=doc_info["url"],
        is_pdf=doc_info["is_pdf"],
    )

    # Print results
    print(f"\n{'=' * 70}")
    print(f"  {ticker} — {config.name}")
    print(f"  Document: {doc_info['doc_type']}")
    print(f"{'=' * 70}")
    print(f"  Extraction confidence: {extraction.extraction_confidence:.2f}")
    print(f"  Fields extracted: {len(extraction.fields_extracted)}")
    print(f"  Fields unavailable: {len(extraction.fields_unavailable)}")
    print(f"  Tokens used: {metadata.get('input_tokens', 0) + metadata.get('output_tokens', 0)}")
    print()

    # Key universal fields
    universal_fields = [
        ("book_value_per_share", extraction.book_value_per_share),
        ("earnings_per_share", extraction.earnings_per_share),
        ("dividends_per_share", extraction.dividends_per_share),
        ("economic_return_pct", extraction.economic_return_pct),
        ("leverage_ratio", extraction.leverage_ratio),
        ("portfolio_size", extraction.portfolio_size),
        ("net_interest_spread", extraction.net_interest_spread),
        ("agency_rmbs_holdings", extraction.agency_rmbs_holdings),
        ("weighted_avg_coupon", extraction.weighted_avg_coupon),
        ("swap_notional", extraction.swap_notional),
    ]

    print("  Key Universal Fields:")
    for name, value in universal_fields:
        status = f"{value}" if value is not None else "—"
        print(f"    {name:30s} = {status}")

    # Company-specific fields
    if any([extraction.non_agency_rmbs_holdings, extraction.residential_loan_portfolio,
            extraction.msr_portfolio, extraction.cmbs_holdings, extraction.origination_volume]):
        print("\n  Non-Agency / Credit Fields:")
        for name in ["non_agency_rmbs_holdings", "residential_loan_portfolio",
                      "msr_portfolio", "cmbs_holdings", "origination_volume"]:
            value = getattr(extraction, name)
            if value is not None:
                print(f"    {name:30s} = {value}")

    # Additional data keys
    if extraction.additional_data:
        print(f"\n  Additional data keys: {list(extraction.additional_data.keys())}")

    # Key highlights
    if extraction.key_highlights:
        print(f"\n  Key highlights ({len(extraction.key_highlights)}):")
        for h in extraction.key_highlights[:3]:
            print(f"    - {h[:120]}")

    # Management commentary (truncated)
    if extraction.management_commentary:
        print(f"\n  Management commentary: {extraction.management_commentary[:200]}...")

    print()
    return extraction


async def main():
    parser = argparse.ArgumentParser(description="Test universal extraction")
    parser.add_argument("--ticker", help="Test a single company (default: all)")
    args = parser.parse_args()

    if args.ticker:
        tickers = [args.ticker.upper()]
    else:
        tickers = list(TEST_DOCUMENTS.keys())

    results = {}
    for ticker in tickers:
        try:
            extraction = await test_single_company(ticker)
            results[ticker] = extraction
        except Exception as e:
            logger.error("FAILED %s: %s", ticker, e, exc_info=True)
            results[ticker] = None

    # Summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    for ticker, extraction in results.items():
        if extraction:
            non_null = sum(
                1 for f in ["book_value_per_share", "earnings_per_share", "leverage_ratio",
                            "portfolio_size", "dividends_per_share"]
                if getattr(extraction, f) is not None
            )
            print(f"  {ticker:6s}  confidence={extraction.extraction_confidence:.2f}  "
                  f"fields={len(extraction.fields_extracted):2d}  "
                  f"key_fields={non_null}/5")
        else:
            print(f"  {ticker:6s}  FAILED")


if __name__ == "__main__":
    asyncio.run(main())
