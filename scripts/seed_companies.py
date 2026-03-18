"""
Seed the companies table with all company configurations.

Usage:
    python -m scripts.seed_companies

Seeds all 6 companies from the company registry. Existing records
are updated on conflict (ticker).
"""

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed")


def seed_companies():
    """Insert or update company records from the multi-company registry."""
    from src.config.company_registry import COMPANY_REGISTRY
    from src.services.supabase_client import get_supabase_client

    client = get_supabase_client()

    for ticker, config in COMPANY_REGISTRY.items():
        logger.info("Seeding %s (%s)...", ticker, config.name)

        # Build scrape_config JSON from the registry
        scrape_config = {
            "document_types": config.document_types,
            "primary_focus": config.primary_focus,
            "has_monthly_update": config.has_monthly_update,
            "has_financial_supplement": config.has_financial_supplement,
            "has_investor_presentation": config.has_investor_presentation,
            "check_cadence": config.check_cadence,
            "notes": config.notes,
            "scrape_sources": [
                {
                    "type": s.type,
                    "url": s.url,
                    "doc_type": s.doc_type,
                    "filing_types": s.filing_types,
                }
                for s in config.scrape_sources
            ],
        }

        record = {
            "ticker": ticker,
            "name": config.name,
            "cik": config.cik,
            "is_active": True,
            "scrape_config": scrape_config,
        }

        # Set URL columns for ARR (backward compat with existing scraper)
        if ticker == "ARR":
            for source in config.scrape_sources:
                if source.doc_type == "monthly_update":
                    record["monthly_updates_url"] = source.url
                elif source.doc_type == "quarterly_earnings":
                    record["quarterly_reports_url"] = source.url
                elif source.doc_type == "press_release":
                    record["news_url"] = source.url

        client.table("companies_ML_REIT").upsert(record, on_conflict="ticker").execute()
        logger.info("  Done.")

    logger.info("Seeding complete — %d companies.", len(COMPANY_REGISTRY))


if __name__ == "__main__":
    seed_companies()
