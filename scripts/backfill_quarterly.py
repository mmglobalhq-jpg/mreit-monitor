"""
Backfill script — loads quarterly earnings releases and 10-Q/10-K filings for ARMOUR.

Usage:
    python -m scripts.backfill_quarterly

Processes:
- 4 years of annual reports (10-K): FY 2022–2025
- ~5 quarters of earnings releases: Q4 2024 – Q4 2025
- ~5 quarters of 10-Q filings: Q1 2025 – Q3 2025, Q1–Q3 2024

Designed to be run once during initial setup.
"""

import asyncio
import logging
from datetime import date

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("backfill_quarterly")

BASE = "https://www.armourreit.com"

# Annual reports (10-K) — 4 years: FY 2022, 2023, 2024, 2025
ANNUAL_REPORTS = [
    {
        "period_label": "FY 2022 10-K",
        "filing_date": date(2023, 2, 28),
        "period_end": "2022-12-31",
        "filing_type": "annual_10k",
        "url": f"{BASE}/static-files/062378a4-df1e-4e5c-a928-05115f6e82d8",
    },
    {
        "period_label": "FY 2023 10-K",
        "filing_date": date(2024, 2, 28),
        "period_end": "2023-12-31",
        "filing_type": "annual_10k",
        "url": f"{BASE}/static-files/549274e0-70f6-414d-8ffe-be6495a98650",
    },
    {
        "period_label": "FY 2024 10-K",
        "filing_date": date(2025, 2, 28),
        "period_end": "2024-12-31",
        "filing_type": "annual_10k",
        "url": f"{BASE}/static-files/9a9fda44-9304-42ec-a5f3-e5434ac9a091",
    },
    {
        "period_label": "FY 2025 10-K",
        "filing_date": date(2026, 2, 28),
        "period_end": "2025-12-31",
        "filing_type": "annual_10k",
        "url": f"{BASE}/static-files/0817cf11-99bc-41f4-9804-b9a9ab177f63",
    },
]

# Quarterly earnings releases — last ~13 months (Q4 2024 – Q4 2025)
EARNINGS_RELEASES = [
    {
        "period_label": "Q4 2024",
        "filing_date": date(2025, 2, 5),
        "url": f"{BASE}/news-releases/news-release-details/armour-residential-reit-inc-announces-q4-results-and-december-0",
    },
    {
        "period_label": "Q1 2025",
        "filing_date": date(2025, 4, 23),
        "url": f"{BASE}/news-releases/news-release-details/armour-residential-reit-inc-announces-q1-results-and-march-31-1",
    },
    {
        "period_label": "Q2 2025",
        "filing_date": date(2025, 7, 23),
        "url": f"{BASE}/news-releases/news-release-details/armour-residential-reit-inc-announces-q2-results-and-june-30-2",
    },
    {
        "period_label": "Q3 2025",
        "filing_date": date(2025, 10, 22),
        "url": f"{BASE}/news-releases/news-release-details/armour-residential-reit-inc-announces-q3-results-and-september-2",
    },
    {
        "period_label": "Q4 2025",
        "filing_date": date(2026, 2, 5),
        "url": f"{BASE}/news-releases/news-release-details/armour-residential-reit-inc-announces-q4-results-and-december-1",
    },
]

# Quarterly 10-Q filings — last ~13 months (Q1 2024 – Q3 2025; Q4s are 10-Ks above)
QUARTERLY_10Q = [
    {
        "period_label": "Q1 2024 10-Q",
        "filing_date": date(2024, 5, 8),
        "period_end": "2024-03-31",
        "url": f"{BASE}/static-files/bf4a39d0-f869-4221-9239-845cc68b64d8",
    },
    {
        "period_label": "Q2 2024 10-Q",
        "filing_date": date(2024, 8, 7),
        "period_end": "2024-06-30",
        "url": f"{BASE}/static-files/2f74c454-36d9-4e0d-a8d8-89f6f755f85b",
    },
    {
        "period_label": "Q3 2024 10-Q",
        "filing_date": date(2024, 11, 6),
        "period_end": "2024-09-30",
        "url": f"{BASE}/static-files/b01b6cf5-949b-4ca5-b402-716efc94f000",
    },
    {
        "period_label": "Q1 2025 10-Q",
        "filing_date": date(2025, 5, 7),
        "period_end": "2025-03-31",
        "url": f"{BASE}/static-files/3ccbaf0d-c629-4b90-836f-e24ee077bc12",
    },
    {
        "period_label": "Q2 2025 10-Q",
        "filing_date": date(2025, 8, 6),
        "period_end": "2025-06-30",
        "url": f"{BASE}/static-files/6aea66f0-8744-4a63-ba99-081140cc23c5",
    },
    {
        "period_label": "Q3 2025 10-Q",
        "filing_date": date(2025, 11, 5),
        "period_end": "2025-09-30",
        "url": f"{BASE}/static-files/365c8574-5ea5-45dc-8b13-71fa4ee7bbea",
    },
]


async def run_backfill():
    """Run the full quarterly backfill for ARMOUR."""
    from src.services.supabase_client import get_supabase_client
    from src.parsers.earnings_release import process_earnings_release
    from src.parsers.quarterly_filing import process_quarterly_filing
    from src.models.schemas import FilingType

    client = get_supabase_client()

    # Get ARMOUR's company_id
    result = client.table("companies").select("id, name").eq("ticker", "ARR").limit(1).execute()
    if not result.data:
        logger.error("ARMOUR (ARR) not found in companies table. Run the migration first.")
        return

    company_id = result.data[0]["id"]
    company_name = result.data[0]["name"]
    ticker = "ARR"

    success_count = 0
    fail_count = 0
    skip_count = 0

    # ========================================================
    # Phase 1: Annual Reports (10-K) — 4 years
    # ========================================================
    logger.info("=" * 60)
    logger.info("PHASE 1: Annual Reports (10-K) — %d filings", len(ANNUAL_REPORTS))
    logger.info("=" * 60)

    for i, filing in enumerate(ANNUAL_REPORTS):
        logger.info("[10-K %d/%d] %s", i + 1, len(ANNUAL_REPORTS), filing["period_label"])

        # Check if already processed
        existing = (
            client.table("filings")
            .select("id, status")
            .eq("company_id", company_id)
            .eq("source_url", filing["url"])
            .execute()
        )
        if existing.data and existing.data[0]["status"] == "completed":
            logger.info("  Already processed — skipping")
            skip_count += 1
            continue

        try:
            await process_quarterly_filing(
                company_id=company_id,
                company_name=company_name,
                ticker=ticker,
                source_url=filing["url"],
                filing_date=filing["filing_date"],
                period_label=filing["period_label"],
                filing_type=FilingType.ANNUAL_10K,
            )
            success_count += 1
            logger.info("  Success!")
        except Exception as e:
            fail_count += 1
            logger.error("  Failed: %s", str(e)[:200])

        await asyncio.sleep(5)

    # ========================================================
    # Phase 2: Earnings Releases — 5 quarters
    # ========================================================
    logger.info("=" * 60)
    logger.info("PHASE 2: Earnings Releases — %d filings", len(EARNINGS_RELEASES))
    logger.info("=" * 60)

    for i, filing in enumerate(EARNINGS_RELEASES):
        logger.info("[Earnings %d/%d] %s", i + 1, len(EARNINGS_RELEASES), filing["period_label"])

        existing = (
            client.table("filings")
            .select("id, status")
            .eq("company_id", company_id)
            .eq("source_url", filing["url"])
            .execute()
        )
        if existing.data and existing.data[0]["status"] == "completed":
            logger.info("  Already processed — skipping")
            skip_count += 1
            continue

        try:
            await process_earnings_release(
                company_id=company_id,
                company_name=company_name,
                ticker=ticker,
                source_url=filing["url"],
                filing_date=filing["filing_date"],
                period_label=filing["period_label"],
            )
            success_count += 1
            logger.info("  Success!")
        except Exception as e:
            fail_count += 1
            logger.error("  Failed: %s", str(e)[:200])

        await asyncio.sleep(5)

    # ========================================================
    # Phase 3: 10-Q Filings — 6 quarters
    # ========================================================
    logger.info("=" * 60)
    logger.info("PHASE 3: 10-Q Filings — %d filings", len(QUARTERLY_10Q))
    logger.info("=" * 60)

    for i, filing in enumerate(QUARTERLY_10Q):
        logger.info("[10-Q %d/%d] %s", i + 1, len(QUARTERLY_10Q), filing["period_label"])

        existing = (
            client.table("filings")
            .select("id, status")
            .eq("company_id", company_id)
            .eq("source_url", filing["url"])
            .execute()
        )
        if existing.data and existing.data[0]["status"] == "completed":
            logger.info("  Already processed — skipping")
            skip_count += 1
            continue

        try:
            await process_quarterly_filing(
                company_id=company_id,
                company_name=company_name,
                ticker=ticker,
                source_url=filing["url"],
                filing_date=filing["filing_date"],
                period_label=filing["period_label"],
                filing_type=FilingType.QUARTERLY_10Q,
            )
            success_count += 1
            logger.info("  Success!")
        except Exception as e:
            fail_count += 1
            logger.error("  Failed: %s", str(e)[:200])

        await asyncio.sleep(5)

    # ========================================================
    # Summary
    # ========================================================
    total = len(ANNUAL_REPORTS) + len(EARNINGS_RELEASES) + len(QUARTERLY_10Q)
    logger.info("=" * 60)
    logger.info(
        "Backfill complete. Success: %d, Failed: %d, Skipped: %d, Total: %d",
        success_count, fail_count, skip_count, total,
    )
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_backfill())
