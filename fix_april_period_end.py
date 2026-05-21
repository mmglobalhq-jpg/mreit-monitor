"""Fix April 2026 ARR extraction period_end: 2026-04-30 -> 2026-03-31."""
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

# Find the April 2026 doc (published 2026-04-22)
april_doc = client.table("reit_company_documents").select("id, document_date, title").eq(
    "company_id", cid
).eq("document_date", "2026-04-22").eq("document_type", "monthly_update").single().execute()
print("April doc:", april_doc.data)

if april_doc.data:
    doc_id = april_doc.data["id"]
    ext = client.table("reit_universal_extractions").select("id, period_end").eq(
        "document_id", doc_id
    ).single().execute()
    print("April extraction:", ext.data)
    if ext.data and ext.data["period_end"] == "2026-04-30":
        r = client.table("reit_universal_extractions").update({"period_end": "2026-03-31"}).eq(
            "id", ext.data["id"]
        ).execute()
        print("Fixed April period_end: 2026-04-30 -> 2026-03-31")
