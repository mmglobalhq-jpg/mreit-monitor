"""
Test extraction script — process a single PDF end-to-end for manual verification.

Usage:
    python -m scripts.test_extraction <pdf_url>
    
Example:
    python -m scripts.test_extraction https://www.armourreit.com/static-files/c40ff395-3917-41f6-8698-19c87315f4bc

This downloads the PDF, runs Claude extraction, prints the structured output,
and optionally runs the comparison if prior data exists.
"""

import asyncio
import json
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("test_extraction")


async def test_single_pdf(url: str):
    """Download and extract data from a single monthly update PDF."""
    from src.services.downloader import download_pdf
    from src.agents.extraction_agent import extract_monthly_update
    
    logger.info("Downloading PDF from %s", url)
    pdf_bytes = await download_pdf(url)
    logger.info("Downloaded %d bytes", len(pdf_bytes))
    
    logger.info("Sending to Claude for extraction...")
    extraction, metadata = await extract_monthly_update(pdf_bytes)
    
    # Pretty print the extraction
    print("\n" + "=" * 80)
    print("EXTRACTION RESULTS")
    print("=" * 80)
    print(json.dumps(extraction.model_dump(), indent=2, default=str))
    
    print("\n" + "=" * 80)
    print("METADATA")
    print("=" * 80)
    print(f"Model: {metadata['model']}")
    print(f"Input tokens: {metadata['input_tokens']}")
    print(f"Output tokens: {metadata['output_tokens']}")
    
    # Summary
    print("\n" + "=" * 80)
    print("QUICK SUMMARY")
    print("=" * 80)
    print(f"Update: {extraction.update_month}")
    print(f"As of: {extraction.data_as_of_date}")
    print(f"Stock Price: ${extraction.key_metrics.stock_price}")
    print(f"Debt/Equity: {extraction.key_metrics.debt_equity}x")
    print(f"Leverage: {extraction.key_metrics.implied_leverage}x")
    print(f"Liquidity: ${extraction.key_metrics.liquidity_millions}M ({extraction.key_metrics.liquidity_pct_capital}%)")
    print(f"Dividend: ${extraction.dividend_info.monthly_dividend} ({extraction.dividend_info.dividend_yield}%)")
    print(f"Portfolio positions: {len(extraction.portfolio_positions)}")
    print(f"Repo counterparties: {len(extraction.repo_positions)}")
    print(f"Swap buckets: {len(extraction.swap_positions)}")
    print(f"Footnotes: {len(extraction.footnotes)}")
    if extraction.unrecognized_data:
        print(f"Unrecognized data: {json.dumps(extraction.unrecognized_data, indent=2)}")
    else:
        print("Unrecognized data: None (all data captured)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Default to the March 2026 update
        url = "https://www.armourreit.com/static-files/c40ff395-3917-41f6-8698-19c87315f4bc"
        logger.info("No URL provided, using default: %s", url)
    else:
        url = sys.argv[1]
    
    asyncio.run(test_single_pdf(url))
