"""Regenerate March and April 2026 ARR monthly summaries."""
import os, sys, asyncio
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()

env_content = open(".env").read()
for line in env_content.splitlines():
    if line.startswith("SUPABASE_URL="):
        os.environ["SUPABASE_URL"] = line.split("=", 1)[1].strip()
    if line.startswith("SUPABASE_SERVICE_KEY="):
        os.environ["SUPABASE_SERVICE_KEY"] = line.split("=", 1)[1].strip()
    if line.startswith("OPENROUTER_API_KEY="):
        os.environ["OPENROUTER_API_KEY"] = line.split("=", 1)[1].strip()

from src.services.supabase_client import get_supabase_client
client = get_supabase_client()

company = client.table("reit_companies").select("id, name").eq("ticker", "ARR").single().execute()
cid = company.data["id"]
cname = company.data["name"]

async def main():
    from src.services.summary_service import generate_monthly_summary
    for year, month, label in [(2026, 3, "March 2026"), (2026, 4, "April 2026")]:
        print(f"\nGenerating {label} summary...")
        try:
            result = await generate_monthly_summary(cid, cname, "ARR", year, month)
            print(f"  OK: {result.get('period_label', '?')} id={result.get('id', '?')}")
        except Exception as e:
            print(f"  FAILED: {e}")

asyncio.run(main())
