"""Check December 2025 ARR doc."""
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

doc = client.table("reit_company_documents").select("id, title, document_date, status, source_url").eq("id", "68d8efd3-e52b-4262-85ae-088778f87c5c").single().execute()
print("Dec doc:", doc.data)

ext = client.table("reit_universal_extractions").select("id, period_end, document_id").eq("document_id", "68d8efd3-e52b-4262-85ae-088778f87c5c").execute()
print("Extractions:", ext.data)
