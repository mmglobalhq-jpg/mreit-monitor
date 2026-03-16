# Claude Code Prompts — REIT Monitor Integration (Step by Step)

## IMPORTANT: Two projects, two Claude Code sessions

You'll run prompts 1-4 in the **REIT Monitor** project, then prompts 5-10 in the **Main Landing** project. Don't mix them.

---

## REIT Monitor Project (`/Users/heathmaxwell/Projects/REIT Monitor/`)

### Prompt 1 — Add frontend API endpoints (Plan Mode)

```
Read CLAUDE.md and src/api/routes.py and src/api/review_app.py.

I'm integrating this backend into a Next.js frontend. I need clean GET endpoints 
for the frontend to consume. The review_app.py already has the logic for querying 
reports and data — use that as reference.

Add these endpoints (in a new file src/api/frontend_routes.py or in routes.py):

1. GET /api/companies — return all active companies with their registry config
2. GET /api/reports?company={ticker}&type={monthly|quarterly|annual}&limit=20 — list reports
3. GET /api/reports/{id} — single full report with report_json
4. GET /api/reports/latest?company={ticker} — most recent report per type for a company
5. GET /api/extractions?company={ticker}&limit=20 — recent extractions
6. GET /api/status — pipeline health (last scrape, pending docs, error counts)

Also add:
- API key auth via X-API-Key header (new env var REIT_MONITOR_API_KEY)
- CORS middleware allowing https://mmglobal.us and http://localhost:3000

Register the new routes in src/main.py. Test that they return data. Commit.
```

### Prompt 2 — Add webhook callback

```
When the summary agent generates a new report, it should POST to an external 
webhook URL to notify the frontend.

1. Add WEBHOOK_URL and WEBHOOK_SECRET env vars to src/config/settings.py
2. In src/agents/summary_agent.py, after a report is stored in Supabase, 
   POST to WEBHOOK_URL with:
   {
     "secret": WEBHOOK_SECRET,
     "report_id": "<uuid>",
     "company_ticker": "<ticker>",
     "company_name": "<name>",
     "report_type": "monthly|quarterly|annual",
     "period_label": "March 2026",
     "overall_summary": "<first 500 chars of the overall summary section>"
   }
3. Make the webhook call fire-and-forget (don't block report generation if it fails).
   Log success/failure but don't raise.
4. If WEBHOOK_URL is not set, skip silently.

Commit.
```

### Prompt 3 — Test locally

```
Start the FastAPI server locally and test all the new endpoints:

1. GET /api/companies — verify it returns the 6 companies
2. GET /api/reports?company=ARR&limit=5 — verify it returns ARMOUR reports
3. GET /api/reports/latest?company=ARR — verify it returns latest per type
4. GET /api/status — verify pipeline health data
5. Test API key auth — verify requests without X-API-Key get 401

Fix any issues. Commit when all endpoints work.
```

### Prompt 4 — Deploy to Railway

```
Deploy this project to Railway:

1. Verify Procfile and railway.toml are correct
2. Verify all required env vars are listed in .env.example
3. List every env var I need to set in Railway's dashboard, with descriptions
4. Push to git and walk me through the Railway deployment steps
5. After deploy, test the health endpoint from the Railway URL

Don't set env vars yourself — just tell me what I need to set and where.
```

---

## Main Landing Project (`/Users/heathmaxwell/Projects/Main Landing Page/`)

### Prompt 5 — Orient + migration (Plan Mode first, then build)

```
Read CLAUDE.md and ARCHITECTURE.md. I'm adding REIT Monitor as App 3 on the dashboard.

Here's the integration spec: [paste the content of reit-monitor-integration-prompt.md 
OR place the file in the project root and say "Read reit-monitor-integration-prompt.md"]

First, tell me what files you'll create/modify. Then:

1. Create supabase/migrations/029_reit_monitor_subscribers.sql with the 
   reit_alert_subscribers table (see spec for schema)
2. Run the migration using the Management API method from CLAUDE.md
3. Create types/reit-monitor.ts with all the TypeScript interfaces
4. Verify the migration succeeded

Commit.
```

### Prompt 6 — API proxy routes + server actions

```
Build the API layer for REIT Monitor:

1. Create a shared proxy helper in lib/reit-monitor/client.ts that:
   - Reads REIT_MONITOR_API_URL and REIT_MONITOR_API_KEY from env
   - Provides a proxyToReitMonitor(path, options?) function
   - Handles errors gracefully

2. Create these API proxy routes:
   - app/api/reit-monitor/companies/route.ts
   - app/api/reit-monitor/reports/route.ts (with query param forwarding)
   - app/api/reit-monitor/reports/[id]/route.ts
   - app/api/reit-monitor/reports/latest/route.ts
   - app/api/reit-monitor/status/route.ts

3. Create the webhook receiver at app/api/reit-monitor/webhook/route.ts that:
   - Validates REIT_WEBHOOK_SECRET
   - Queries reit_alert_subscribers for matching subscribers
   - Sends email to each via Resend (use existing Resend setup)
   - Returns 200

4. Create server actions in lib/actions/reit-monitor.ts:
   - listSubscriptions()
   - addSubscription(email, companyTickers, reportTypes)
   - updateSubscription(id, updates)
   - removeSubscription(id)
   - getCompanies()
   - getReports(filters)
   - getReport(id)
   - getPipelineStatus()

Auth-gate everything — use createClient() from lib/supabase/server.ts 
to verify the user is authenticated before proxying.

Commit.
```

### Prompt 7 — Dashboard card update

```
Update app/(app)/dashboard/page.tsx:

Replace the App 3 placeholder with:
{
  title: "REIT Monitor",
  description: "mREIT securities analysis & reporting",
  href: "/reit-monitor",
  icon: TrendingUp  // from lucide-react
}

Keep everything else identical. Verify it builds. Commit.
```

### Prompt 8 — Main REIT Monitor page

```
Create app/(app)/reit-monitor/page.tsx — the main REIT Monitor page.

Layout (top to bottom):

1. Page header: "REIT Monitor" title + gear icon linking to /reit-monitor/settings

2. Company cards row (horizontal scrollable on mobile, grid on desktop):
   - 6 cards for ARR, BMNM, CIM, AGNC, NLY, DX
   - Each shows: ticker (large), company name (small), latest report date
   - Clickable — sets a filter for the report list below
   - Selected card gets the red accent border
   - "All" option to clear filter

3. Report type filter: buttons/tabs for All | Monthly | Quarterly | Annual

4. Report list: a table or card list showing filtered reports
   - Columns: Company (ticker), Type (badge), Period, Generated Date
   - Click row → navigate to /reit-monitor/[id]
   - If no reports: "No reports available yet" empty state

5. Pipeline status bar at bottom: "Last updated: {time} · {n} companies active"

Fetch data using the server actions from lib/actions/reit-monitor.ts.
If the REIT Monitor backend isn't reachable, show a friendly error state 
instead of crashing.

Style EXACTLY like the existing app — use the same card styles from dashboard:
- bg-[#131316] border-[#2A2A30]
- hover:border-[#BA0C2F]/40
- text-[#FAFAFA] and text-[#A1A1AA]
- Use shadcn Card, Badge, Button, Table components

Commit.
```

### Prompt 9 — Report detail page + settings page

```
Build two more pages:

1. app/(app)/reit-monitor/[id]/page.tsx — Single report view
   - Back button → /reit-monitor
   - Header: company name, ticker, report type badge, period label, date
   - 6 sections from report_json, each as a collapsible card:
     * Overall Summary
     * Securities Detail
     * Filing Highlights
     * Performance & Activity
     * Supplemental Materials
     * Data Gaps
   - Sections with data_available=false: muted styling (text-[#666], italic, dashed border)
   - Render section content as markdown using react-markdown (already installed)
   - Source documents listed at bottom of each section

2. app/(app)/reit-monitor/settings/page.tsx — Email subscription management
   - Back button → /reit-monitor
   - "Email Alert Subscriptions" header
   - List current user's subscriptions (from server action):
     * Email, companies (chips), report types (chips)
     * Toggle active/inactive (shadcn Switch)
     * Delete button
   - "Add Subscription" form:
     * Email input (pre-fill with user's email from auth)
     * Company checkboxes (all 6 + "All Companies" master toggle)
     * Report type checkboxes (monthly, quarterly, annual)
     * Save button
   - Toast notifications (sonner) for success/error

Same dark theme styling. Commit.
```

### Prompt 10 — Build, lint, update ARCHITECTURE.md

```
Final steps:

1. Run npm run build — fix any errors
2. Run npm run lint — fix any warnings
3. Update ARCHITECTURE.md with all new:
   - Pages (/reit-monitor, /reit-monitor/[id], /reit-monitor/settings)
   - API routes (/api/reit-monitor/*)
   - Server actions (lib/actions/reit-monitor.ts)
   - Database table (reit_alert_subscribers)
   - Types (types/reit-monitor.ts)
   - External service (REIT Monitor API on Railway)
   - New env vars (REIT_MONITOR_API_URL, REIT_MONITOR_API_KEY, REIT_WEBHOOK_SECRET)
4. Verify everything builds clean
5. Commit with message "feat: add REIT Monitor as App 3 with reports, alerts, and settings"
```
