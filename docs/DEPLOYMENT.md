# Deployment Guide — mREIT Monitor

## Prerequisites

1. **Supabase Pro** project with:
   - PostgreSQL database (run migrations)
   - Storage bucket named `filings`
   - Service role key (not anon key — we need server-side access)

2. **Anthropic API key** with access to Sonnet and Opus models

3. **Resend account** with:
   - Verified sending domain
   - API key

4. **Railway Pro account**

## Supabase Setup

1. Create a new Supabase project (or use existing)
2. Run the migration:
   ```bash
   # Via Supabase CLI
   supabase db push --file supabase/migrations/001_initial_schema.sql
   
   # Or paste into the SQL Editor in the Supabase dashboard
   ```
3. Create a storage bucket named `filings` (can be private)
4. Copy the project URL and service role key to your `.env`

## Local Development

```bash
# Clone the repo
cd mreit-monitor

# Create .env from template
cp .env.example .env
# Fill in your values

# Install dependencies (using uv)
uv sync

# Or with pip
pip install -e ".[dev]"

# Run locally
uvicorn src.main:app --reload --port 8000

# Test health check
curl http://localhost:8000/health
```

## Railway Deployment

1. Connect your GitHub repo to Railway
2. Railway auto-detects the `Procfile` and `railway.toml`
3. Set environment variables in Railway dashboard:
   - All variables from `.env.example`
   - Railway provides `PORT` automatically
4. Deploy

## Running the Backfill

After deployment and database setup:

```bash
# Run the backfill script to load 12 months of ARMOUR monthly updates
python scripts/backfill_armour.py

# Or trigger via API
curl -X POST https://your-app.railway.app/trigger/backfill/ARR
```

## Monitoring

- **Health check:** `GET /health` — returns 200 if app is running
- **Railway logs:** Check Railway dashboard for scheduler and processing logs
- **Supabase:** Check `poll_log` table for polling history, `filings` table for processing status
- **Email:** You'll receive an email alert for each successfully processed filing

## Cost Estimates

| Service | Monthly Cost | Notes |
|---------|-------------|-------|
| Railway Pro | ~$5-10 | Low CPU usage, mostly idle between polls |
| Supabase Pro | $25 | Database + storage |
| Anthropic API | ~$5-15 | ~13 monthly PDFs × $0.05 each + comparison calls |
| Resend | Free tier | <100 emails/month |
| **Total** | **~$35-50/month** | |
