from src.services.supabase_client import get_supabase_client
from collections import defaultdict
client = get_supabase_client()

# Get company id -> ticker map
companies = client.table('reit_companies').select('id,ticker').execute().data
id_to_ticker = {c['id']: c['ticker'] for c in companies}

# Last EDGAR poll per company
print("=== Last EDGAR poll per ticker ===")
polls = client.table('reit_poll_log').select('company_id,poll_type,completed_at,new_filings_found,error_message') \
    .eq('poll_type', 'edgar').order('completed_at', desc=True).limit(50).execute().data
seen = set()
for p in polls:
    cid = p['company_id']
    if cid not in seen:
        seen.add(cid)
        ticker = id_to_ticker.get(cid, cid[:8])
        err = f"  ERROR: {p['error_message'][:80]}" if p['error_message'] else ""
        print(f"  {ticker}: {(p['completed_at'] or '')[:19]}  new={p['new_filings_found']}{err}")

# Companies with no EDGAR poll at all
for cid, ticker in id_to_ticker.items():
    if cid not in seen:
        print(f"  {ticker}: NO EDGAR POLL FOUND")

# Detected docs by date bucket
print("\n=== Detected docs by month ===")
docs = client.table('reit_company_documents').select('status,document_date') \
    .eq('status', 'detected').execute().data
buckets = defaultdict(int)
for d in docs:
    dt = (d.get('document_date') or '')[:7]  # YYYY-MM
    buckets[dt] += 1
for ym in sorted(buckets, reverse=True)[:20]:
    print(f"  {ym}: {buckets[ym]}")

# How many detected are pre-2025-07-01
pre = sum(1 for d in docs if (d.get('document_date') or '') < '2025-07-01')
keep = sum(1 for d in docs if (d.get('document_date') or '') >= '2025-07-01')
print(f"\nWill KEEP (>= 2025-07-01): {keep}")
print(f"Will SKIP (<  2025-07-01): {pre}")

# All statuses summary
print("\n=== All doc statuses ===")
all_docs = client.table('reit_company_documents').select('status').execute().data
status_counts = defaultdict(int)
for d in all_docs:
    status_counts[d['status']] += 1
for status, count in sorted(status_counts.items()):
    print(f"  {status}: {count}")
