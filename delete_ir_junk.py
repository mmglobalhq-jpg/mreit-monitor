"""Delete all failed investor_relations docs for DX and NLY — these are legacy IR scraper junk."""
from supabase import create_client
import os

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
companies = sb.from_("reit_companies").select("id,ticker").execute()

for c in companies.data:
    if c["ticker"] not in ("DX", "NLY"):
        continue
    result = sb.from_("reit_company_documents").delete().eq("company_id", c["id"]).eq("document_type", "investor_relations").eq("status", "failed").execute()
    print(f"Deleted {len(result.data)} failed investor_relations docs for {c['ticker']}")
