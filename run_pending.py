"""One-shot: process all currently detected docs. No scheduler, no polling."""
import asyncio
import logging
import sys
from datetime import date as date_cls, datetime as datetime_cls, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    stream=sys.stdout,
)

async def main():
    from src.config.company_registry import get_company_config
    from src.models.database import get_active_companies
    from src.parsers.universal_document_processor import process_document
    from src.services.supabase_client import get_supabase_client

    client = get_supabase_client()

    pending = (
        client.table("reit_company_documents")
        .select("id, company_id, source_url, document_type, document_date, title, created_at")
        .eq("status", "detected")
        .eq("document_type", "annual_10k")
        .gte("document_date", "2025-01-01")
        .lt("document_date", "2026-01-01")
        .is_("raw_content", "null")
        .execute()
    ).data

    print(f"\nFound {len(pending)} detected docs to process\n")
    if not pending:
        return

    companies = {c["id"]: c for c in get_active_companies()}

    for i, doc in enumerate(pending, 1):
        company_id = doc["company_id"]
        co = companies.get(company_id)
        if not co:
            print(f"[{i}/{len(pending)}] SKIP — unknown company_id {company_id}")
            continue

        ticker = co["ticker"]
        registry_config = get_company_config(ticker)
        if not registry_config:
            print(f"[{i}/{len(pending)}] SKIP — no registry config for {ticker}")
            continue

        raw_date = doc.get("document_date")
        document_date = date_cls.fromisoformat(raw_date[:10]) if raw_date else date_cls.today()

        print(f"[{i}/{len(pending)}] Processing {ticker} {doc['document_type']} {raw_date} ...")
        try:
            ok = await process_document(
                company_id=company_id,
                company_name=co["name"],
                ticker=ticker,
                company_config=registry_config,
                source_url=doc["source_url"],
                document_type=doc["document_type"],
                document_date=document_date,
                period_label="",
                title=doc.get("title", ""),
                skip_email=True,
            )
            print(f"[{i}/{len(pending)}] {'OK' if ok else 'FAILED'} — {ticker} {doc['document_type']}")
        except Exception as e:
            print(f"[{i}/{len(pending)}] ERROR — {ticker} {doc['document_type']}: {e}")

    # Final tally
    remaining = (
        client.table("reit_company_documents")
        .select("status")
        .eq("status", "detected")
        .execute()
    ).data
    print(f"\nDone. {len(remaining)} docs still detected.")

asyncio.run(main())
