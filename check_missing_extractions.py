"""Check which ARR monthly_update docs are missing extractions."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from src.services.supabase_client import get_supabase_client

client = get_supabase_client()
company = client.table('reit_companies').select('id').eq('ticker', 'ARR').single().execute()
cid = company.data['id']

docs = client.table('reit_company_documents').select('id, title, document_date, status').eq('company_id', cid).eq('document_type', 'monthly_update').order('document_date').execute()
print('All ARR monthly_update docs:')
for d in docs.data:
    print("  {} | {:10s} | {} | {}".format(d['document_date'], d['status'], d['id'], d['title']))

ext = client.table('reit_universal_extractions').select('document_id, period_end').eq('company_id', cid).eq('document_type', 'monthly_update').order('period_end').execute()
ext_doc_ids = {e['document_id'] for e in ext.data}
print()
print('Extractions exist for:', sorted([e['period_end'] for e in ext.data]))

print()
print('Docs with NO extraction:')
for d in docs.data:
    if d['id'] not in ext_doc_ids:
        print("  {} | {} | {}".format(d['document_date'], d['title'], d['id']))
