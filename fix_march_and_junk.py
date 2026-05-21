"""
1. Delete the 99 junk detected docs for ARR from 2026-05-21.
2. Re-extract March 2026 Company Update via /trigger/extract.
"""
import os, sys, asyncio, httpx
sys.path.insert(0, os.path.dirname(__file__))

from src.services.supabase_client import get_supabase_client
from dotenv import load_dotenv
load_dotenv()

client = get_supabase_client()
company = client.table('reit_companies').select('id, name').eq('ticker', 'ARR').single().execute()
cid = company.data['id']

# --- Step 1: Delete junk detected docs from today ---
junk = client.table('reit_company_documents').select('id').eq('company_id', cid).eq('status', 'detected').eq('document_date', '2026-05-21').execute()
junk_ids = [r['id'] for r in junk.data]
print("Junk docs to delete:", len(junk_ids))
if junk_ids:
    result = client.table('reit_company_documents').delete().in_('id', junk_ids).execute()
    print("Deleted:", len(result.data or []))

# --- Step 2: Re-extract March 2026 ---
march_doc = client.table('reit_company_documents').select('id, source_url, document_type').eq('id', '5904f0c4-11f7-4f06-809b-456695550ce1').single().execute()
march_url = march_doc.data['source_url']
print("\nMarch 2026 source_url:", march_url)

api_key = os.getenv('REIT_MONITOR_API_KEY', '')
if not api_key:
    # Try reading directly from .env
    for line in open('.env'):
        if line.startswith('REIT_MONITOR_API_KEY='):
            api_key = line.strip().split('=', 1)[1]
            break

print("API key length:", len(api_key))

async def reextract():
    async with httpx.AsyncClient(timeout=300.0) as http:
        resp = await http.post(
            'http://127.0.0.1:8012/trigger/extract',
            json={"ticker": "ARR", "source_url": march_url, "document_type": "monthly_update"},
            headers={"X-API-Key": api_key},
        )
        print("Response:", resp.status_code, resp.text[:300])

asyncio.run(reextract())
