from supabase import create_client
import os
from collections import Counter

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
companies = sb.from_("reit_companies").select("id,ticker,name").eq("is_active", True).execute()
for c in sorted(companies.data, key=lambda x: x["ticker"]):
    docs = sb.from_("reit_company_documents").select("document_type, status").eq("company_id", c["id"]).execute()
    counts = Counter((r["document_type"], r["status"]) for r in docs.data)
    total = len(docs.data)
    completed = sum(v for (dt, st), v in counts.items() if st == "completed")
    detected = sum(v for (dt, st), v in counts.items() if st == "detected")
    failed = sum(v for (dt, st), v in counts.items() if st == "failed")
    print(c["ticker"], "total=" + str(total), "completed=" + str(completed), "detected=" + str(detected), "failed=" + str(failed))
