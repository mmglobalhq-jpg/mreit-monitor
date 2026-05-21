"""Fix period_end on December 2025 ARR extraction: 2025-12-31 -> 2025-11-30."""
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

EXTRACTION_ID = "0df3da48-890b-43af-b0f0-66fd3dde60b7"

result = client.table("reit_universal_extractions").update({"period_end": "2025-11-30"}).eq("id", EXTRACTION_ID).execute()
print("Updated:", result.data)

# Verify
row = client.table("reit_universal_extractions").select("id, period_end, document_id").eq("id", EXTRACTION_ID).single().execute()
print("After fix:", row.data)
