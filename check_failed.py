from supabase import create_client
import os
from collections import Counter

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
companies = sb.from_("reit_companies").select("id,ticker").execute()
company_map = {c["id"]: c["ticker"] for c in companies.data}

for ticker in ["DX", "NLY"]:
    cid = next(c["id"] for c in companies.data if c["ticker"] == ticker)
    docs = sb.from_("reit_company_documents").select("document_type, title, document_date, source_url").eq("company_id", cid).eq("status", "failed").execute()
    print(f"\n=== {ticker} failed ({len(docs.data)}) ===")
    for d in docs.data:
        print(f"  {d['document_date']}  {d['document_type']:<30}  {d['title'][:60]}")
        print(f"    {d['source_url'][:90]}")
