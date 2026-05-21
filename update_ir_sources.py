"""
One-shot: fix reit_company_sources for AGNC, NLY, DX so the IR poller
maps them to investor_presentation doc_type correctly.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from src.services.supabase_client import get_supabase_client

client = get_supabase_client()

updates = [
    {
        "filter": {"ticker": "AGNC", "source_type": "investor_relations"},
        "update": {"source_type": "presentations"},
        "label": "AGNC investor_relations -> presentations",
    },
    {
        "filter": {"ticker": "NLY", "source_type": "investor_relations"},
        "update": {"source_type": "presentations"},
        "label": "NLY investor_relations -> presentations",
    },
    {
        "filter": {"ticker": "DX", "url": "https://www.dynexcapital.com/investors/news-events/presentations"},
        "update": {"source_type": "presentations"},
        "label": "DX presentations page source_type -> presentations",
    },
    {
        "filter": {"ticker": "DX", "url": "https://www.dynexcapital.com/investors"},
        "update": {"active": False},
        "label": "DX /investors homepage -> inactive",
    },
]

for u in updates:
    query = client.table("reit_company_sources").update(u["update"])
    for k, v in u["filter"].items():
        query = query.eq(k, v)
    result = query.execute()
    rows = result.data or []
    print("  {}: {} row(s) updated".format(u["label"], len(rows)))

print("\nVerification -- active website sources for AGNC, DX, NLY:")
rows = (
    client.table("reit_company_sources")
    .select("ticker, source_type, label, url, active")
    .in_("ticker", ["AGNC", "DX", "NLY"])
    .eq("active", True)
    .neq("source_type", "edgar")
    .execute()
).data

for r in rows:
    print("  [{}] {:<30} {}".format(r["ticker"], r["source_type"], r["url"]))
