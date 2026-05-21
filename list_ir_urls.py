from supabase import create_client
import os

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
companies = sb.from_("reit_companies").select("id,ticker,name").eq("is_active", True).execute()

for c in sorted(companies.data, key=lambda x: x["ticker"]):
    if c["ticker"] == "ARR":
        continue
    sources = sb.from_("reit_company_sources").select("url, source_type, label").eq("company_id", c["id"]).eq("active", True).execute()
    print(f"\n{c['ticker']} — {c['name']}")
    for s in sources.data:
        print(f"  [{s['source_type']}] {s['label']}  ->  {s['url']}")
