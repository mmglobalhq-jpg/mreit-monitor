"""Extract all detected ARR monthly_update and investor_presentation docs."""
import asyncio
import logging
import sys
from datetime import date

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", stream=sys.stdout)

DOCS = [
    ("2026-05-15", "May 2026 Company Update",           "https://www.armourreit.com/static-files/844f941e-16c3-425d-a5ad-2a5a33ad8cda", "monthly_update"),
    ("2026-04-23", "Q1 2026 Investor Presentation",     "https://www.armourreit.com/static-files/f7d78b4c-0642-4940-aac2-55c314c4810b", "investor_presentation"),
    ("2026-04-22", "April 2026 Company Update",         "https://www.armourreit.com/static-files/c645dd3f-7f5e-4a4c-8edb-9bef6e1b8858", "monthly_update"),
    ("2026-03-13", "March 2026 Company Update",         "https://www.armourreit.com/static-files/c40ff395-3917-41f6-8698-19c87315f4bc", "monthly_update"),
    ("2026-02-18", "Q4 2025 Investor Presentation",     "https://www.armourreit.com/static-files/a3d43d3f-556e-49b3-8432-c285ddd92cb0", "investor_presentation"),
    ("2026-02-18", "February 2026 Company Update",      "https://www.armourreit.com/static-files/68039465-ebb5-49ba-8cc6-33e6f20ba32e", "monthly_update"),
    ("2026-01-16", "January 2026 Company Update",       "https://www.armourreit.com/static-files/6b3741b5-1cb3-4f01-8895-e8903e64b8d0", "monthly_update"),
    ("2025-12-12", "December 2025 Company Update",      "https://www.armourreit.com/static-files/1942b9f3-78b4-44b8-bea5-b9f3251a49ac", "monthly_update"),
    ("2025-11-14", "November 2025 Company Update",      "https://www.armourreit.com/static-files/3288975d-7fbf-4b9a-99a0-695ade9f9c42", "monthly_update"),
    ("2025-10-22", "October 2025 Company Update",       "https://www.armourreit.com/static-files/50a84238-6dd3-4051-a3ee-3ea7a8276791", "monthly_update"),
    ("2025-09-12", "September 2025 Company Update",     "https://www.armourreit.com/static-files/a6cc08fe-f154-4a7a-b7b1-699cfd08335e", "monthly_update"),
    ("2025-08-15", "August 2025 Company Update",        "https://www.armourreit.com/static-files/d090ab31-c67a-4dc2-880e-42904355425c", "monthly_update"),
    ("2025-07-23", "July 2025 Company Update",          "https://www.armourreit.com/static-files/5cd266ad-2264-4207-9370-d17b09d160c2", "monthly_update"),
    ("2025-06-13", "June 2025 Company Update",          "https://www.armourreit.com/static-files/6352ff4f-4019-4cd8-9875-043b51bffc3a", "monthly_update"),
    ("2025-05-16", "May 2025 Company Update",           "https://www.armourreit.com/static-files/a9e91427-7c9e-4886-8aaf-a8b4a13c4ae7", "monthly_update"),
    ("2025-04-23", "April 2025 Company Update",         "https://www.armourreit.com/static-files/2e359796-86ae-4c9a-9cce-47fc8ff2bcb2", "monthly_update"),
    ("2025-03-13", "March 2025 Company Update",         "https://www.armourreit.com/static-files/d0ebe47c-bc3c-4db7-9211-4765d82a3d71", "monthly_update"),
    ("2025-02-12", "February 2025 Company Update",      "https://www.armourreit.com/static-files/700c2a09-89ac-48f9-9448-935ba763f77f", "monthly_update"),
    ("2025-01-17", "January 2025 Company Update",       "https://www.armourreit.com/static-files/3e591f21-0dfc-4b09-b7a9-705acbeeec79", "monthly_update"),
]

async def main():
    from src.parsers.universal_document_processor import process_document
    from src.models.database import get_active_companies
    from src.config.company_registry import get_company_config

    companies = {c["ticker"]: c for c in get_active_companies()}
    arr = companies["ARR"]
    arr_config = get_company_config("ARR")

    print(f"Extracting {len(DOCS)} ARR documents with google/gemini-2.5-flash-lite\n")

    ok_count = 0
    fail_count = 0
    for i, (doc_date, title, url, doc_type) in enumerate(DOCS, 1):
        print(f"[{i}/{len(DOCS)}] {title} ...")
        try:
            ok = await process_document(
                company_id=arr["id"],
                company_name=arr["name"],
                ticker="ARR",
                company_config=arr_config,
                source_url=url,
                document_type=doc_type,
                document_date=date.fromisoformat(doc_date),
                period_label="",
                title=title,
                skip_email=True,
            )
            if ok:
                ok_count += 1
                print(f"[{i}/{len(DOCS)}] OK")
            else:
                fail_count += 1
                print(f"[{i}/{len(DOCS)}] FAILED")
        except Exception as e:
            fail_count += 1
            print(f"[{i}/{len(DOCS)}] ERROR: {e}")

    print(f"\nDone: {ok_count} succeeded, {fail_count} failed.")

asyncio.run(main())
