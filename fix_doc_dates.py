"""Fix document_date overwritten by re-extraction, and period_end issues."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()

env_content = open(".env").read()
for line in env_content.splitlines():
    if line.startswith("SUPABASE_URL="):
        os.environ["SUPABASE_URL"] = line.split("=", 1)[1].strip()
    if line.startswith("SUPABASE_SERVICE_KEY="):
        os.environ["SUPABASE_SERVICE_KEY"] = line.split("=", 1)[1].strip()

from src.services.supabase_client import get_supabase_client
client = get_supabase_client()

company = client.table("reit_companies").select("id").eq("ticker", "ARR").single().execute()
cid = company.data["id"]

# Fix the March 2026 doc that got its document_date overwritten to 2026-05-21
# It should be 2026-03-13 (the actual publication date of the March update)
# The doc is the one with period_end=2026-02-28 AND document_date=2026-05-21
march_ext = client.table("reit_universal_extractions").select("document_id").eq(
    "company_id", cid
).eq("document_type", "monthly_update").eq("period_end", "2026-02-28").execute()
print("March 2026 extraction docs:", march_ext.data)

if march_ext.data:
    doc_id = march_ext.data[0]["document_id"]
    doc = client.table("reit_company_documents").select("id, document_date, title").eq("id", doc_id).single().execute()
    print("Current doc:", doc.data)
    if doc.data["document_date"] == "2026-05-21":
        r = client.table("reit_company_documents").update({
            "document_date": "2026-03-13",
            "title": "March 2026 Company Update",
        }).eq("id", doc_id).execute()
        print("Fixed March doc:", r.data[0]["document_date"], r.data[0]["title"])
    else:
        print("March doc already has correct date:", doc.data["document_date"])

# Fix May 2026 period_end=2026-05-31 -> 2026-04-30
# Published 2026-05-15 means it contains April data
may_ext = client.table("reit_universal_extractions").select("id, document_id, period_end").eq(
    "company_id", cid
).eq("document_type", "monthly_update").eq("period_end", "2026-05-31").execute()
print("\nMay 2026 extraction (period_end=2026-05-31):", may_ext.data)

if may_ext.data:
    # Verify by checking the doc date
    for row in may_ext.data:
        doc = client.table("reit_company_documents").select("id, document_date, title").eq("id", row["document_id"]).single().execute()
        print("  Doc:", doc.data)
        if doc.data and doc.data.get("document_date") == "2026-05-15":
            # Published May 15 -> data as of April 30
            r = client.table("reit_universal_extractions").update({"period_end": "2026-04-30"}).eq("id", row["id"]).execute()
            print("  Fixed May extraction period_end: 2026-05-31 -> 2026-04-30")
        else:
            print("  Skipping — unexpected doc date")
