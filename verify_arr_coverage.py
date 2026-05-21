"""Verify ARR monthly_update extraction coverage."""
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

docs = client.table("reit_company_documents").select(
    "id, title, document_date, status"
).eq("company_id", cid).eq("document_type", "monthly_update").gte("document_date", "2025-01-01").order("document_date").execute()

exts = client.table("reit_universal_extractions").select(
    "document_id, period_end"
).eq("company_id", cid).eq("document_type", "monthly_update").order("period_end").execute()
ext_map = {e["document_id"]: e["period_end"] for e in exts.data}

print("ARR monthly_update docs (2025+):")
print(f"  {'document_date':<14} {'status':<12} {'title':<35} {'period_end'}")
print("  " + "-"*85)
for d in docs.data:
    pe = ext_map.get(d["id"], "(no extraction)")
    print(f"  {d['document_date']:<14} {d['status']:<12} {d['title'][:35]:<35} {pe}")
