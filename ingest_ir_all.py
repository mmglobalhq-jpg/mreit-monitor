"""Ingest all 2025-2026 investor presentations for AGNC, DX, NLY, CIM."""
import asyncio
import logging
import sys
from datetime import date

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", stream=sys.stdout)

DOCS = {
    "AGNC": [
        ("2025-01-28", "Q4 2024 Stockholder Presentation", "https://investors.agnc.com/static-files/30ec38d9-7a1b-4ff4-a70a-7c8b733bd41f", "investor_presentation"),
        ("2025-04-22", "Q1 2025 Stockholder Presentation", "https://investors.agnc.com/static-files/debb487b-1a82-4c30-84fe-4d8096e5c18f", "investor_presentation"),
        ("2025-07-22", "Q2 2025 Stockholder Presentation", "https://investors.agnc.com/static-files/d589e9ee-1c5f-4654-babe-4546f58710a2", "investor_presentation"),
        ("2025-10-21", "Q3 2025 Stockholder Presentation", "https://investors.agnc.com/static-files/b9b1e30f-f655-4181-95e8-e1f8a4fba53e", "investor_presentation"),
        ("2026-01-27", "Q4 2025 Stockholder Presentation", "https://investors.agnc.com/static-files/44088892-7d86-4491-956b-83b20d4bb521", "investor_presentation"),
        ("2026-04-21", "Q1 2026 Stockholder Presentation", "https://investors.agnc.com/static-files/e88a34ae-38f8-4d2a-be9d-ff783bb0be08", "investor_presentation"),
    ],
    "DX": [
        ("2025-01-27", "Q4 2024 Earnings Presentation", "https://d1io3yog0oux5.cloudfront.net/_d16349b595d4a839032ec03d95ed5e9b/dynexcapital/db/928/10024/pdf/DX-Q424-Earnings-Presentation-Final.pdf", "investor_presentation"),
        ("2025-04-21", "Q1 2025 Earnings Presentation", "https://d1io3yog0oux5.cloudfront.net/_d16349b595d4a839032ec03d95ed5e9b/dynexcapital/db/928/10033/pdf/1Q25+Investor+Deck_Earnings+Presentation+FINAL.pdf", "investor_presentation"),
        ("2025-07-21", "Q2 2025 Earnings Presentation", "https://d1io3yog0oux5.cloudfront.net/_d16349b595d4a839032ec03d95ed5e9b/dynexcapital/db/928/10058/pdf/2Q25+Investor+Deck_Earnings+Presentation+%283%29.pdf", "investor_presentation"),
        ("2025-10-20", "Q3 2025 Earnings Presentation", "https://d1io3yog0oux5.cloudfront.net/_d16349b595d4a839032ec03d95ed5e9b/dynexcapital/db/928/10073/pdf/3Q25+Investor+Deck_Earnings+Presentation+%282%29.pdf", "investor_presentation"),
        ("2026-01-26", "Q4 2025 Earnings Presentation", "https://d1io3yog0oux5.cloudfront.net/_d16349b595d4a839032ec03d95ed5e9b/dynexcapital/db/928/10082/pdf/4Q25+Investor+Deck_Earnings+Presentation+%284%29.pdf", "investor_presentation"),
        ("2026-04-20", "Q1 2026 Earnings Presentation", "https://d1io3yog0oux5.cloudfront.net/_d16349b595d4a839032ec03d95ed5e9b/dynexcapital/db/928/10106/pdf/DX+Q126+Earnings+Presentation+FINAL.pdf", "investor_presentation"),
    ],
    "NLY": [
        ("2025-02-18", "Residential Credit Presentation Feb 2025", "https://www.annaly.com/~/media/Files/A/Annaly-V3/documents/residential-credit-presentation-february-2025.pdf", "investor_presentation"),
        ("2025-04-30", "Q1 2025 Investor Presentation",      "https://www.annaly.com/~/media/Files/A/Annaly-V3/documents/q1-2025-investor-presentation.pdf", "investor_presentation"),
        ("2025-04-30", "Q1 2025 Financial Supplement",       "https://www.annaly.com/~/media/Files/A/Annaly-V3/documents/q1-2025-financial-supplement.pdf", "investor_presentation"),
        ("2025-07-23", "Q2 2025 Investor Presentation",      "https://www.annaly.com/~/media/Files/A/Annaly-V3/documents/2q-2025-investor-presentation.pdf", "investor_presentation"),
        ("2025-07-23", "Q2 2025 Financial Supplement",       "https://www.annaly.com/~/media/Files/A/Annaly-V3/documents/q2-2025-financial-supplement.pdf", "investor_presentation"),
        ("2025-10-02", "Residential Credit Presentation Oct 2025", "https://www.annaly.com/~/media/Files/A/Annaly-V3/Residential%20Credit%20Presentation%20-%20October%202025%20-%20FINAL.pdf", "investor_presentation"),
        ("2025-10-22", "Q3 2025 Investor Presentation",      "https://www.annaly.com/~/media/Files/A/Annaly-V3/documents/q3-2025-investor-presentation.pdf", "investor_presentation"),
        ("2025-10-22", "Q3 2025 Financial Supplement",       "https://www.annaly.com/~/media/Files/A/Annaly-V3/documents/q3-2025-financial-supplement.pdf", "investor_presentation"),
        ("2026-01-28", "Q4 2025 Investor Presentation",      "https://www.annaly.com/~/media/Files/A/Annaly-V3/documents/q4-2025-investor-presentation.pdf", "investor_presentation"),
        ("2026-01-28", "Q4 2025 Financial Supplement",       "https://www.annaly.com/~/media/Files/A/Annaly-V3/documents/q4-2025-financial-supplement.pdf", "investor_presentation"),
        ("2026-02-18", "Residential Credit Presentation Feb 2026", "https://www.annaly.com/~/media/Files/A/Annaly-V3/documents/residential-credit-presentation-feb-2026.pdf", "investor_presentation"),
        ("2026-04-21", "Q1 2026 Investor Presentation",      "https://www.annaly.com/~/media/Files/A/Annaly-V3/documents/q1-2026-investor-presentation.pdf", "investor_presentation"),
        ("2026-04-21", "Q1 2026 Financial Supplement",       "https://www.annaly.com/~/media/Files/A/Annaly-V3/documents/q1-2026-financial-supplement.pdf", "investor_presentation"),
    ],
    "CIM": [
        ("2025-02-12", "Q4 2024 Investor Presentation",      "https://www.chimerareit.com/_assets/_bc3641b2a7e474499cea58527f2cbbb8/chimerareit/db/982/10186/pdf/Q4%2724+Investor+Presentation.pdf", "investor_presentation"),
        ("2025-03-03", "RBC Conference Presentation",        "https://www.chimerareit.com/_assets/_bc3641b2a7e474499cea58527f2cbbb8/chimerareit/db/982/10187/pdf/RBC+Investor+Presentation.pdf", "investor_presentation"),
        ("2025-05-08", "Q1 2025 Investor Presentation",      "https://www.chimerareit.com/_assets/_bc3641b2a7e474499cea58527f2cbbb8/chimerareit/db/982/10196/pdf/Q1%2725+Investor+Presentation_vFINAL_a11y.pdf", "investor_presentation"),
        ("2025-06-12", "HomeXpress Overview",                "https://www.chimerareit.com/_assets/_bc3641b2a7e474499cea58527f2cbbb8/chimerareit/db/982/10208/pdf/Overview_HomeXpress.pdf", "investor_presentation"),
        ("2025-08-06", "Q2 2025 Investor Presentation",      "https://www.chimerareit.com/_assets/_bc3641b2a7e474499cea58527f2cbbb8/chimerareit/db/982/10214/pdf/Q2%2725+Investor+Presentation.pdf", "investor_presentation"),
        ("2025-11-06", "Q3 2025 Investor Presentation",      "https://www.chimerareit.com/_assets/_bc3641b2a7e474499cea58527f2cbbb8/chimerareit/db/982/10233/pdf/Q3+2025+Investor+Presentation.pdf", "investor_presentation"),
        ("2026-02-11", "Q4 2025 Investor Presentation",      "https://www.chimerareit.com/_assets/_bc3641b2a7e474499cea58527f2cbbb8/chimerareit/db/982/10250/pdf/Q4%2725+Investor+Presentation_a11y.pdf", "investor_presentation"),
        ("2026-02-20", "Q4 2025 SFIG Conference Presentation", "https://www.chimerareit.com/_assets/_bc3641b2a7e474499cea58527f2cbbb8/chimerareit/db/982/10260/pdf/Q4%2725_SFIG+Conf_v7_a11y.pdf", "investor_presentation"),
        ("2026-05-07", "Q1 2026 Investor Presentation",      "https://www.chimerareit.com/_assets/_bc3641b2a7e474499cea58527f2cbbb8/chimerareit/db/982/10267/pdf/Q1%2726+Investor+Presentation_Final.pdf", "investor_presentation"),
    ],
}


async def main():
    from src.parsers.universal_document_processor import process_document
    from src.models.database import get_active_companies
    from src.config.company_registry import get_company_config

    companies = {c["ticker"]: c for c in get_active_companies()}

    total_docs = sum(len(v) for v in DOCS.values())
    print(f"Ingesting {total_docs} IR documents across {len(DOCS)} companies\n")

    from src.services.supabase_client import get_supabase_client
    sb = get_supabase_client()

    ok_total = 0
    fail_total = 0
    skip_total = 0

    for ticker, docs in DOCS.items():
        company = companies[ticker]
        config = get_company_config(ticker)
        print(f"\n{'='*60}")
        print(f"{ticker} — {len(docs)} documents")
        print(f"{'='*60}")

        ok_count = 0
        fail_count = 0
        skip_count = 0
        for i, (doc_date, title, url, doc_type) in enumerate(docs, 1):
            # Skip docs already completed
            existing = sb.from_("reit_company_documents").select("id, status").eq("company_id", company["id"]).eq("document_type", doc_type).eq("source_url", url).limit(1).execute()
            if existing.data and existing.data[0]["status"] == "completed":
                skip_count += 1
                print(f"  [{i}/{len(docs)}] SKIP (already completed): {title}")
                continue
            print(f"  [{i}/{len(docs)}] {title} ...")
            try:
                ok = await process_document(
                    company_id=company["id"],
                    company_name=company["name"],
                    ticker=ticker,
                    company_config=config,
                    source_url=url,
                    document_type=doc_type,
                    document_date=date.fromisoformat(doc_date),
                    period_label="",
                    title=title,
                    skip_email=True,
                )
                if ok:
                    ok_count += 1
                    print(f"  [{i}/{len(docs)}] OK")
                else:
                    fail_count += 1
                    print(f"  [{i}/{len(docs)}] FAILED")
            except Exception as e:
                fail_count += 1
                print(f"  [{i}/{len(docs)}] ERROR: {e}")

        print(f"{ticker}: {ok_count} OK, {fail_count} failed, {skip_count} skipped")
        ok_total += ok_count
        fail_total += fail_count
        skip_total += skip_count

    print(f"\n{'='*60}")
    print(f"Total: {ok_total} succeeded, {fail_total} failed, {skip_total} skipped")


asyncio.run(main())
