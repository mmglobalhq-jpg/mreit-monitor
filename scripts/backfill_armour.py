"""
Backfill script — loads 12 months of ARMOUR monthly company updates.

Usage:
    python -m scripts.backfill_armour

This script:
1. Reads the backfill URLs from src/config/companies.py
2. For each monthly PDF (oldest first):
   a. Downloads the PDF
   b. Runs the extraction pipeline
   c. Runs the comparison agent (skipped for the first month)
   d. Stores everything in Supabase
3. Rate-limits Claude API calls to avoid hitting limits

Designed to be run once during initial setup.
"""

import asyncio
import logging
import time
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("backfill")


async def run_backfill():
    """Run the full 12-month backfill for ARMOUR."""
    from src.config.companies import ARMOUR_MONTHLY_BACKFILL
    from src.services.supabase_client import get_supabase_client
    from src.parsers.monthly_update import process_monthly_update
    
    client = get_supabase_client()
    
    # Get ARMOUR's company_id from Supabase
    result = client.table("companies").select("id, name").eq("ticker", "ARR").limit(1).execute()
    if not result.data:
        logger.error("ARMOUR (ARR) not found in companies table. Run the migration first.")
        return
    
    company_id = result.data[0]["id"]
    company_name = result.data[0]["name"]
    ticker = "ARR"
    
    logger.info("Starting backfill for %s (%s)", company_name, ticker)
    logger.info("Processing %d monthly updates...", len(ARMOUR_MONTHLY_BACKFILL))
    
    success_count = 0
    fail_count = 0
    
    for i, (period_key, filing_date_str, url) in enumerate(ARMOUR_MONTHLY_BACKFILL):
        filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d").date()
        
        # Convert period_key to label (e.g., "2025-03" → "March 2025")
        dt = datetime.strptime(period_key, "%Y-%m")
        period_label = dt.strftime("%B %Y")
        
        logger.info(
            "[%d/%d] Processing %s (filed %s)...",
            i + 1, len(ARMOUR_MONTHLY_BACKFILL), period_label, filing_date_str,
        )
        
        # Check if already processed
        existing = (
            client.table("filings")
            .select("id, status")
            .eq("company_id", company_id)
            .eq("source_url", url)
            .execute()
        )
        
        if existing.data and existing.data[0]["status"] == "completed":
            logger.info("  Already processed — skipping")
            success_count += 1
            continue
        
        try:
            await process_monthly_update(
                company_id=company_id,
                company_name=company_name,
                ticker=ticker,
                source_url=url,
                filing_date=filing_date,
                period_label=period_label,
            )
            success_count += 1
            logger.info("  Success!")
        except Exception as e:
            fail_count += 1
            logger.error("  Failed: %s", str(e))
        
        # Rate limit: wait between API calls
        if i < len(ARMOUR_MONTHLY_BACKFILL) - 1:
            logger.info("  Waiting 5 seconds before next...")
            await asyncio.sleep(5)
    
    logger.info(
        "Backfill complete. Success: %d, Failed: %d, Total: %d",
        success_count, fail_count, len(ARMOUR_MONTHLY_BACKFILL),
    )


if __name__ == "__main__":
    asyncio.run(run_backfill())
