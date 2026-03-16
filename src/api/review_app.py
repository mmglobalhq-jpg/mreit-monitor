"""
Review web app for previewing summary reports before enabling email delivery.

Serves HTML pages at /review/ that list and render summary reports.
The generate form dynamically limits options to periods with actual data.
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger("mreit-monitor.review_app")

review_router = APIRouter(prefix="/review", tags=["review"])


# ============================================================================
# Data availability helpers
# ============================================================================

def _get_available_periods() -> dict:
    """
    Query what data periods are available per company.

    Returns dict keyed by ticker, each value is:
      {
        "name": "ARMOUR Residential REIT",
        "monthly": [{"year": 2026, "month": 3, "label": "March 2026"}, ...],
        "quarterly": [{"year": 2025, "quarter": 4, "label": "Q4 2025"}, ...],
        "annual": [{"year": 2025, "label": "FY 2025"}, ...],
      }
    """
    from src.services.supabase_client import get_supabase_client

    client = get_supabase_client()
    companies = client.table("companies").select("id, ticker, name").eq("is_active", True).execute().data
    co_map = {co["id"]: co for co in companies}

    result = {}

    for co in companies:
        ticker = co["ticker"]
        result[ticker] = {"name": co["name"], "monthly": [], "quarterly": [], "annual": []}

    # Monthly: from monthly_metrics (ARR) or universal_extractions with monthly types
    monthly_rows = client.table("monthly_metrics").select("company_id, as_of_date").order("as_of_date", desc=True).execute().data
    seen_monthly = set()
    for row in monthly_rows:
        co = co_map.get(row["company_id"])
        if not co:
            continue
        ticker = co["ticker"]
        d = row["as_of_date"]
        # as_of_date is end-of-month; the report month is the next month
        from datetime import date as date_cls, timedelta
        if isinstance(d, str):
            parts = d.split("-")
            dt = date_cls(int(parts[0]), int(parts[1]), int(parts[2]))
        else:
            dt = d
        # The report month is the month after the as_of_date
        report_dt = dt + timedelta(days=3)  # bump into the next month
        key = (ticker, report_dt.year, report_dt.month)
        if key not in seen_monthly:
            seen_monthly.add(key)
            month_name = report_dt.strftime("%B %Y")
            result[ticker]["monthly"].append({
                "year": report_dt.year,
                "month": report_dt.month,
                "label": month_name,
            })

    # Quarterly: from quarterly_metrics + universal_extractions
    quarterly_rows = client.table("quarterly_metrics").select("company_id, period_end_date, quarter_label").order("period_end_date", desc=True).execute().data
    seen_quarterly = set()
    for row in quarterly_rows:
        co = co_map.get(row["company_id"])
        if not co:
            continue
        ticker = co["ticker"]
        label = row["quarter_label"]
        # Parse "Q4 2025"
        parts = label.replace("Q", "").split()
        if len(parts) == 2:
            q, y = int(parts[0]), int(parts[1])
            key = (ticker, y, q)
            if key not in seen_quarterly:
                seen_quarterly.add(key)
                result[ticker]["quarterly"].append({
                    "year": y,
                    "quarter": q,
                    "label": label,
                })

    # Also check universal_extractions for quarterly data (new companies)
    ue_rows = client.table("universal_extractions").select("company_id, fiscal_year, fiscal_quarter, period_end").order("period_end", desc=True).execute().data
    for row in ue_rows:
        co = co_map.get(row["company_id"])
        if not co:
            continue
        ticker = co["ticker"]
        q = row.get("fiscal_quarter")
        y = row.get("fiscal_year")
        if q and y:
            key = (ticker, y, q)
            if key not in seen_quarterly:
                seen_quarterly.add(key)
                result[ticker]["quarterly"].append({
                    "year": y,
                    "quarter": q,
                    "label": f"Q{q} {y}",
                })

    # Annual: any company with quarterly data covering a full year
    for ticker, data in result.items():
        years_with_data = set()
        for entry in data["quarterly"]:
            years_with_data.add(entry["year"])
        for entry in data["monthly"]:
            years_with_data.add(entry["year"])
        for y in sorted(years_with_data, reverse=True):
            data["annual"].append({"year": y, "label": f"FY {y}"})

    return result


# ============================================================================
# HTML Templates
# ============================================================================

LIST_PAGE_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<title>mREIT Monitor — Report Review</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1a1a1a; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 20px; }}
    h1 {{ font-size: 24px; font-weight: 600; }}
    .subtitle {{ color: #666; font-size: 14px; margin-bottom: 24px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
    th {{ text-align: left; padding: 10px 12px; background: #f5f5f5; border-bottom: 2px solid #ddd; font-weight: 600; font-size: 14px; }}
    td {{ padding: 10px 12px; border-bottom: 1px solid #eee; font-size: 14px; }}
    tr:hover {{ background: #fafafa; }}
    a {{ color: #0066cc; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 500; }}
    .badge-monthly {{ background: #e3f2fd; color: #1565c0; }}
    .badge-quarterly {{ background: #e8f5e9; color: #2e7d32; }}
    .badge-annual {{ background: #fff3e0; color: #e65100; }}
    .badge-sent {{ background: #e8f5e9; color: #2e7d32; }}
    .badge-pending {{ background: #fff3e0; color: #e65100; }}
    .generate-section {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 24px 0; }}
    .generate-section h2 {{ font-size: 16px; margin-top: 0; }}
    .btn {{ display: inline-block; padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 500; text-decoration: none; }}
    .btn-primary {{ background: #0066cc; color: white; }}
    .btn-primary:hover {{ background: #0052a3; text-decoration: none; }}
    .btn-sm {{ padding: 4px 10px; font-size: 12px; }}
    .btn-send {{ background: #2e7d32; color: white; }}
    .btn-send:hover {{ background: #1b5e20; }}
    form.inline {{ display: inline; }}
    .actions {{ display: flex; gap: 8px; }}
    select, input {{ padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px; }}
    select:disabled {{ background: #eee; color: #999; }}
    .no-data {{ font-size: 12px; color: #999; margin-top: 4px; }}
    .pending-section {{ background: #fff8e1; padding: 20px; border-radius: 8px; margin: 24px 0; border: 1px solid #ffe082; }}
    .pending-section h2 {{ font-size: 16px; margin-top: 0; color: #e65100; }}
    .pending-card {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background: white; border-radius: 6px; margin: 8px 0; border: 1px solid #eee; }}
    .pending-card-info {{ flex: 1; }}
    .pending-card-ticker {{ font-weight: 600; font-size: 15px; }}
    .pending-card-docs {{ font-size: 13px; color: #666; margin-top: 4px; }}
    .badge-detected {{ background: #fff3e0; color: #e65100; }}
    .btn-process {{ background: #e65100; color: white; }}
    .btn-process:hover {{ background: #bf360c; text-decoration: none; }}
</style>
</head>
<body>
    <h1>mREIT Monitor — Report Review</h1>
    <p class="subtitle">Preview and manage summary reports before email delivery</p>

    <div class="generate-section">
        <h2>Generate New Report</h2>
        <form id="genForm" action="/review/generate" method="post" style="display: flex; gap: 12px; align-items: end; flex-wrap: wrap;">
            <div>
                <label style="font-size: 12px; color: #666;">Ticker</label><br>
                <select name="ticker" id="tickerSelect">{ticker_options}</select>
            </div>
            <div>
                <label style="font-size: 12px; color: #666;">Type</label><br>
                <select name="report_type" id="typeSelect"></select>
            </div>
            <div id="periodGroup">
                <label style="font-size: 12px; color: #666;" id="periodLabel">Period</label><br>
                <select name="period" id="periodSelect"></select>
            </div>
            <input type="hidden" name="year" id="yearInput">
            <button type="submit" class="btn btn-primary" id="genBtn">Generate</button>
        </form>
        <div id="noDataMsg" class="no-data" style="display:none;">No data available for this selection.</div>
    </div>

    {pending_section}

    <h2 style="font-size: 18px;">Existing Reports</h2>
    <table>
        <tr>
            <th>Ticker</th>
            <th>Period</th>
            <th>Type</th>
            <th>Model</th>
            <th>Tokens</th>
            <th>Email</th>
            <th>Created</th>
            <th>Actions</th>
        </tr>
        {report_rows}
    </table>

    {no_reports_msg}

    <script>
    var avail = {available_json};

    var tickerSel = document.getElementById('tickerSelect');
    var typeSel   = document.getElementById('typeSelect');
    var periodSel = document.getElementById('periodSelect');
    var yearInput = document.getElementById('yearInput');
    var periodLabel = document.getElementById('periodLabel');
    var genBtn    = document.getElementById('genBtn');
    var noDataMsg = document.getElementById('noDataMsg');

    function rebuildSelect(selectEl, items) {{
        while (selectEl.firstChild) selectEl.removeChild(selectEl.firstChild);
        for (var i = 0; i < items.length; i++) {{
            var opt = document.createElement('option');
            opt.value = items[i].value;
            opt.textContent = items[i].text;
            if (items[i].dataYear !== undefined) {{
                opt.setAttribute('data-year', items[i].dataYear);
            }}
            selectEl.appendChild(opt);
        }}
    }}

    function updateTypes() {{
        var ticker = tickerSel.value;
        var data = avail[ticker] || {{}};

        var items = [];
        if (data.monthly && data.monthly.length > 0) items.push({{value: 'monthly', text: 'Monthly'}});
        if (data.quarterly && data.quarterly.length > 0) items.push({{value: 'quarterly', text: 'Quarterly'}});
        if (data.annual && data.annual.length > 0) items.push({{value: 'annual', text: 'Annual'}});

        if (items.length === 0) {{
            rebuildSelect(typeSel, [{{value: '', text: 'No data'}}]);
            typeSel.disabled = true;
            genBtn.disabled = true;
            noDataMsg.style.display = 'block';
        }} else {{
            rebuildSelect(typeSel, items);
            typeSel.disabled = false;
            genBtn.disabled = false;
            noDataMsg.style.display = 'none';
        }}
        updatePeriods();
    }}

    function updatePeriods() {{
        var ticker = tickerSel.value;
        var rtype  = typeSel.value;
        var data   = avail[ticker] || {{}};
        var periods = data[rtype] || [];

        var items = [];
        if (rtype === 'monthly') {{
            periodLabel.textContent = 'Month';
            for (var i = 0; i < periods.length; i++) {{
                items.push({{value: periods[i].month, text: periods[i].label, dataYear: periods[i].year}});
            }}
        }} else if (rtype === 'quarterly') {{
            periodLabel.textContent = 'Quarter';
            for (var i = 0; i < periods.length; i++) {{
                items.push({{value: periods[i].quarter, text: periods[i].label, dataYear: periods[i].year}});
            }}
        }} else if (rtype === 'annual') {{
            periodLabel.textContent = 'Year';
            for (var i = 0; i < periods.length; i++) {{
                items.push({{value: 1, text: periods[i].label, dataYear: periods[i].year}});
            }}
        }}

        if (items.length === 0) {{
            rebuildSelect(periodSel, [{{value: '', text: '—'}}]);
            periodSel.disabled = true;
            genBtn.disabled = true;
        }} else {{
            rebuildSelect(periodSel, items);
            periodSel.disabled = false;
            genBtn.disabled = false;
        }}
        updateYear();
    }}

    function updateYear() {{
        var selected = periodSel.options[periodSel.selectedIndex];
        if (selected && selected.getAttribute('data-year')) {{
            yearInput.value = selected.getAttribute('data-year');
        }}
    }}

    tickerSel.addEventListener('change', updateTypes);
    typeSel.addEventListener('change', updatePeriods);
    periodSel.addEventListener('change', updateYear);

    updateTypes();
    </script>
</body>
</html>"""

REPORT_VIEW_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<title>mREIT Monitor — {period_label} {report_type_label} Summary</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1a1a1a; line-height: 1.6; max-width: 720px; margin: 0 auto; padding: 20px; }}
    h1 {{ font-size: 22px; font-weight: 600; margin-bottom: 4px; }}
    h2 {{ font-size: 17px; font-weight: 600; margin-top: 28px; margin-bottom: 8px; color: #333; border-bottom: 1px solid #eee; padding-bottom: 4px; }}
    .subtitle {{ color: #666; font-size: 14px; margin-bottom: 24px; }}
    .nav {{ margin-bottom: 20px; }}
    .nav a {{ color: #0066cc; text-decoration: none; font-size: 14px; }}
    .section {{ margin: 16px 0; }}
    .section-content {{ background: #f8f9fa; padding: 16px; border-radius: 8px; margin: 8px 0; font-size: 14px; white-space: pre-wrap; word-wrap: break-word; }}
    .unavailable {{ color: #999; font-style: italic; background: #f0f0f0; }}
    .source-docs {{ font-size: 12px; color: #888; margin-top: 4px; }}
    .btn {{ display: inline-block; padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 500; text-decoration: none; }}
    .btn-send {{ background: #2e7d32; color: white; }}
    .btn-send:hover {{ background: #1b5e20; text-decoration: none; }}
    .btn-back {{ background: #f5f5f5; color: #333; }}
    .btn-back:hover {{ background: #e0e0e0; text-decoration: none; }}
    .actions {{ margin-top: 24px; display: flex; gap: 12px; }}
    .meta {{ background: #f0f0f0; padding: 12px 16px; border-radius: 6px; font-size: 13px; color: #666; margin-bottom: 20px; }}
</style>
</head>
<body>
    <div class="nav"><a href="/review/">&larr; Back to all reports</a></div>

    <h1>{company_name} ({ticker})</h1>
    <p class="subtitle">{report_type_label} Summary — {period_label}</p>

    <div class="meta">
        Model: {model_used} | Tokens: {tokens_used} | Generated: {created_at}
        {email_status}
    </div>

    {sections_html}

    <div class="actions">
        <a href="/review/" class="btn btn-back">Back</a>
        <form action="/review/{report_id}/send" method="post" style="display: inline;">
            <button type="submit" class="btn btn-send">Send Email</button>
        </form>
    </div>
</body>
</html>"""


# ============================================================================
# Routes
# ============================================================================

@review_router.get("/", response_class=HTMLResponse)
async def list_reports():
    """List all summary reports with a dynamic generate form."""
    from src.services.supabase_client import get_supabase_client

    client = get_supabase_client()
    result = (
        client.table("summary_reports")
        .select("id, company_id, report_type, period_label, model_used, tokens_used, email_sent, email_sent_at, created_at, report_json")
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )

    # Map company_ids to tickers
    companies = client.table("companies").select("id, ticker").execute().data
    co_map = {co["id"]: co["ticker"] for co in companies}

    report_rows = ""
    for r in result.data:
        badge_class = f"badge-{r['report_type']}"
        email_badge = '<span class="badge badge-sent">Sent</span>' if r.get("email_sent") else '<span class="badge badge-pending">Pending</span>'
        created = r.get("created_at", "")[:16].replace("T", " ")
        ticker = r.get("report_json", {}).get("ticker") or co_map.get(r.get("company_id"), "—")

        report_rows += f"""
        <tr>
            <td><strong>{ticker}</strong></td>
            <td><a href="/review/{r['id']}">{r['period_label']}</a></td>
            <td><span class="badge {badge_class}">{r['report_type']}</span></td>
            <td style="font-size: 12px; color: #888;">{r.get('model_used', '—')}</td>
            <td>{r.get('tokens_used', '—')}</td>
            <td>{email_badge}</td>
            <td style="font-size: 13px; color: #666;">{created}</td>
            <td class="actions">
                <a href="/review/{r['id']}" class="btn btn-primary btn-sm">View</a>
                <form action="/review/{r['id']}/send" method="post" class="inline">
                    <button type="submit" class="btn btn-send btn-sm">Send</button>
                </form>
            </td>
        </tr>"""

    no_reports_msg = ""
    if not result.data:
        no_reports_msg = '<p style="color: #999; text-align: center; padding: 40px;">No summary reports generated yet. Use the form above to create one.</p>'

    # Build pending filings section
    pending_docs = (
        client.table("company_documents")
        .select("id, company_id, document_type, source_url, title, document_date, created_at")
        .eq("status", "detected")
        .order("created_at", desc=True)
        .execute()
    ).data

    pending_section = ""
    if pending_docs:
        # Group by company
        by_company = {}
        for doc in pending_docs:
            ticker = co_map.get(doc["company_id"], "?")
            if ticker not in by_company:
                by_company[ticker] = []
            by_company[ticker].append(doc)

        cards_html = ""
        for ticker in sorted(by_company.keys()):
            docs = by_company[ticker]
            doc_list = ", ".join(d.get("title") or d.get("document_type", "?") for d in docs)
            cards_html += f"""
            <div class="pending-card">
                <div class="pending-card-info">
                    <span class="pending-card-ticker">{ticker}</span>
                    <span class="badge badge-detected">{len(docs)} pending</span>
                    <div class="pending-card-docs">{doc_list}</div>
                </div>
                <form action="/review/process/{ticker}" method="post" style="display: inline;">
                    <button type="submit" class="btn btn-process btn-sm">Update Filings</button>
                </form>
            </div>"""

        pending_section = f"""
        <div class="pending-section">
            <h2>Pending Filings</h2>
            <p style="font-size: 13px; color: #666; margin-top: 0;">New filings detected. Click "Update Filings" to download and extract.</p>
            {cards_html}
        </div>"""

    # Build available periods for the form
    available = _get_available_periods()
    available_json = json.dumps(available)

    # Build ticker <option> tags
    ticker_options = ""
    for ticker in sorted(available.keys()):
        name = available[ticker]["name"]
        ticker_options += f'<option value="{ticker}">{ticker} — {name}</option>\n'

    html = LIST_PAGE_TEMPLATE.format(
        report_rows=report_rows,
        no_reports_msg=no_reports_msg,
        available_json=available_json,
        ticker_options=ticker_options,
        pending_section=pending_section,
    )
    return HTMLResponse(content=html)


@review_router.get("/{report_id}", response_class=HTMLResponse)
async def view_report(report_id: str):
    """View a single summary report rendered as HTML."""
    # Route ab-test to its handler (defined later) to avoid path capture
    if report_id == "ab-test":
        return await ab_test_page()

    from src.services.supabase_client import get_supabase_client

    client = get_supabase_client()
    result = (
        client.table("summary_reports")
        .select("*")
        .eq("id", report_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Report not found")

    report = result.data[0]
    report_json = report.get("report_json", {})

    # Build sections HTML
    sections_html = ""
    section_keys = [
        ("overall_summary", "Overall Summary"),
        ("securities_detail", "Securities Detail"),
        ("filing_highlights", "Filing Highlights"),
        ("performance_activity", "Performance & Activity"),
        ("supplemental_materials", "Supplemental Materials"),
        ("data_gaps", "Data Gaps & Notes"),
    ]

    for key, title in section_keys:
        section = report_json.get(key, {})
        content = section.get("content", "No content available.")
        data_available = section.get("data_available", True)
        source_docs = section.get("source_documents", [])

        css_class = "section-content" if data_available else "section-content unavailable"
        sources_html = ""
        if source_docs:
            sources_html = f'<div class="source-docs">Sources: {", ".join(source_docs)}</div>'

        sections_html += f"""
        <h2>{title}</h2>
        <div class="section">
            <div class="{css_class}">{content}</div>
            {sources_html}
        </div>"""

    email_status = ""
    if report.get("email_sent"):
        sent_at = (report.get("email_sent_at") or "")[:16].replace("T", " ")
        email_status = f" | Email sent: {sent_at}"

    created_at = (report.get("created_at") or "")[:16].replace("T", " ")

    html = REPORT_VIEW_TEMPLATE.format(
        company_name=report_json.get("company_name", "—"),
        ticker=report_json.get("ticker", "—"),
        report_type_label=report.get("report_type", "").title(),
        period_label=report.get("period_label", "—"),
        model_used=report.get("model_used", "—"),
        tokens_used=report.get("tokens_used", "—"),
        created_at=created_at,
        email_status=email_status,
        sections_html=sections_html,
        report_id=report_id,
    )
    return HTMLResponse(content=html)


@review_router.post("/{report_id}/send")
async def send_report_email(report_id: str):
    """Send the summary report via email."""
    from src.services.supabase_client import get_supabase_client
    from src.services.email_service import init_resend
    from src.config.settings import settings
    from src.agents.prompts.summary_templates import SUMMARY_EMAIL_SUBJECT, SUMMARY_EMAIL_BODY
    import resend

    client = get_supabase_client()
    result = (
        client.table("summary_reports")
        .select("*")
        .eq("id", report_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Report not found")

    report = result.data[0]
    report_json = report.get("report_json", {})

    # Build sections HTML for email
    sections_html = ""
    section_keys = [
        ("overall_summary", "Overall Summary"),
        ("securities_detail", "Securities Detail"),
        ("filing_highlights", "Filing Highlights"),
        ("performance_activity", "Performance & Activity"),
        ("supplemental_materials", "Supplemental Materials"),
        ("data_gaps", "Data Gaps & Notes"),
    ]

    for key, title in section_keys:
        section = report_json.get(key, {})
        content = section.get("content", "No content available.")
        data_available = section.get("data_available", True)
        css_class = "section-content" if data_available else "section-content unavailable"

        sections_html += f'<h2>{title}</h2><div class="{css_class}">{content}</div>'

    report_type_label = report.get("report_type", "").title()
    subject = SUMMARY_EMAIL_SUBJECT.format(
        ticker=report_json.get("ticker", ""),
        period_label=report.get("period_label", ""),
        report_type_label=report_type_label,
    )

    body = SUMMARY_EMAIL_BODY.format(
        company_name=report_json.get("company_name", ""),
        ticker=report_json.get("ticker", ""),
        report_type_label=report_type_label,
        period_label=report.get("period_label", ""),
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        sections_html=sections_html,
    )

    init_resend()
    try:
        email_result = resend.Emails.send({
            "from": settings.alert_email_from,
            "to": [settings.alert_email_to],
            "subject": subject,
            "html": body,
        })
        logger.info("Summary email sent for report %s (id: %s)", report_id, email_result.get("id"))
    except Exception as e:
        logger.error("Failed to send summary email: %s", e)
        raise HTTPException(status_code=500, detail=f"Email send failed: {e}")

    # Mark as sent
    client.table("summary_reports").update({
        "email_sent": True,
        "email_sent_at": datetime.utcnow().isoformat(),
    }).eq("id", report_id).execute()

    # Redirect back to the report view
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/review/{report_id}", status_code=303)


@review_router.post("/process/{ticker}")
async def process_pending_filings(ticker: str):
    """Process all detected (pending) filings for a company."""
    from src.config.company_registry import get_company_config
    from src.models.database import get_company_by_ticker
    from src.parsers.universal_document_processor import process_document
    from src.services.supabase_client import get_supabase_client

    company = get_company_by_ticker(ticker.upper())
    if not company:
        raise HTTPException(status_code=404, detail=f"Company {ticker.upper()} not found")

    config = get_company_config(ticker.upper())
    if not config:
        raise HTTPException(status_code=400, detail=f"No registry config for {ticker.upper()}")

    client = get_supabase_client()
    pending = (
        client.table("company_documents")
        .select("*")
        .eq("company_id", company["id"])
        .eq("status", "detected")
        .execute()
    ).data

    if not pending:
        logger.info("No pending filings for %s", ticker.upper())
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/review/", status_code=303)

    logger.info("Processing %d pending filings for %s", len(pending), ticker.upper())

    from datetime import date as date_cls

    for doc in pending:
        try:
            doc_date = None
            if doc.get("document_date"):
                raw = doc["document_date"]
                if isinstance(raw, str):
                    doc_date = date_cls.fromisoformat(raw[:10])
                else:
                    doc_date = raw
            else:
                doc_date = date_cls.today()

            await process_document(
                company_id=company["id"],
                company_name=company["name"],
                ticker=ticker.upper(),
                company_config=config,
                source_url=doc["source_url"],
                document_type=doc["document_type"],
                document_date=doc_date,
                period_label=doc.get("title") or doc.get("document_type", ""),
                title=doc.get("title", ""),
                skip_email=True,
            )
        except Exception as e:
            logger.error(
                "Failed to process %s %s: %s",
                ticker.upper(), doc.get("title", doc["source_url"][:60]), e,
            )

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/review/", status_code=303)


@review_router.post("/generate")
async def generate_from_form(
    ticker: str = Form(),
    report_type: str = Form(),
    year: int = Form(),
    period: int = Form(),
):
    """Handle the generate form submission from the review UI."""
    from src.models.database import get_company_by_ticker
    from src.services.summary_service import (
        generate_monthly_summary,
        generate_quarterly_summary,
        generate_annual_summary,
    )

    company = get_company_by_ticker(ticker)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company {ticker.upper()} not found")

    if report_type == "monthly":
        await generate_monthly_summary(
            company_id=company["id"],
            company_name=company["name"],
            ticker=company["ticker"],
            year=year,
            month=period,
        )
    elif report_type == "quarterly":
        await generate_quarterly_summary(
            company_id=company["id"],
            company_name=company["name"],
            ticker=company["ticker"],
            year=year,
            quarter=period,
        )
    elif report_type == "annual":
        await generate_annual_summary(
            company_id=company["id"],
            company_name=company["name"],
            ticker=company["ticker"],
            year=year,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown report type: {report_type}")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/review/", status_code=303)


# ============================================================================
# A/B Test Page — Compare extraction models
# ============================================================================

AB_TEST_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<title>mREIT Monitor — A/B Model Test</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1a1a1a; line-height: 1.6; max-width: 1100px; margin: 0 auto; padding: 20px; }}
    h1 {{ font-size: 24px; font-weight: 600; }}
    .subtitle {{ color: #666; font-size: 14px; margin-bottom: 24px; }}
    .nav {{ margin-bottom: 20px; }}
    .nav a {{ color: #0066cc; text-decoration: none; font-size: 14px; }}
    .form-section {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 24px 0; }}
    .form-section h2 {{ font-size: 16px; margin-top: 0; }}
    select, input {{ padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px; }}
    .btn {{ display: inline-block; padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 500; text-decoration: none; }}
    .btn-primary {{ background: #0066cc; color: white; }}
    .btn-primary:hover {{ background: #0052a3; }}
    .checkbox-group {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 8px 0; }}
    .checkbox-group label {{ font-size: 14px; display: flex; align-items: center; gap: 4px; }}
    .results {{ margin-top: 24px; }}
    .results-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
    .result-card {{ background: white; border: 1px solid #ddd; border-radius: 8px; padding: 16px; }}
    .result-card h3 {{ font-size: 15px; margin-top: 0; }}
    .result-card .meta {{ font-size: 12px; color: #888; margin-bottom: 12px; }}
    .metric-row {{ display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; border-bottom: 1px solid #f0f0f0; }}
    .metric-label {{ color: #666; }}
    .metric-value {{ font-weight: 500; }}
    .match {{ color: #2e7d32; }}
    .mismatch {{ color: #c62828; font-weight: 600; }}
    .cost {{ font-size: 13px; font-weight: 600; margin-top: 8px; }}
    .cost-savings {{ color: #2e7d32; }}
</style>
</head>
<body>
    <div class="nav"><a href="/review/">&larr; Back to reports</a></div>
    <h1>A/B Model Comparison</h1>
    <p class="subtitle">Compare extraction accuracy and cost across different AI models</p>

    <div class="form-section">
        <h2>Select Document & Models</h2>
        <form action="/review/ab-test" method="post" style="display: flex; flex-direction: column; gap: 12px;">
            <div>
                <label style="font-size: 12px; color: #666;">Document (already processed)</label><br>
                <select name="document_id" style="min-width: 400px;">
                    {document_options}
                </select>
            </div>
            <div>
                <label style="font-size: 12px; color: #666;">Models to compare</label>
                <div class="checkbox-group">
                    <label><input type="checkbox" name="models" value="claude-sonnet-4-20250514" checked> Claude Sonnet 4</label>
                    <label><input type="checkbox" name="models" value="gpt-4.1-mini"> GPT-4.1 Mini</label>
                    <label><input type="checkbox" name="models" value="gpt-4o-mini"> GPT-4o Mini</label>
                    <label><input type="checkbox" name="models" value="gemini-2.5-flash"> Gemini 2.5 Flash</label>
                    <label><input type="checkbox" name="models" value="gemini-2.0-flash"> Gemini 2.0 Flash</label>
                </div>
            </div>
            <div>
                <button type="submit" class="btn btn-primary" id="runBtn" onclick="this.textContent='Running... (30-60s per model)'; this.disabled=true; this.form.submit();">Run Comparison</button>
            </div>
        </form>
    </div>

    {results_html}
</body>
</html>"""


@review_router.get("/ab-test", response_class=HTMLResponse)
async def ab_test_page():
    """A/B test page for comparing extraction models."""
    from src.services.supabase_client import get_supabase_client

    client = get_supabase_client()
    companies = client.table("companies").select("id, ticker").execute().data
    co_map = {co["id"]: co["ticker"] for co in companies}

    docs = (
        client.table("company_documents")
        .select("id, company_id, document_type, title, document_date, source_url")
        .eq("status", "completed")
        .order("document_date", desc=True)
        .limit(50)
        .execute()
    ).data

    document_options = ""
    for doc in docs:
        ticker = co_map.get(doc["company_id"], "?")
        title = doc.get("title") or doc.get("document_type", "?")
        date_str = (doc.get("document_date") or "")[:10]
        document_options += f'<option value="{doc["id"]}">{ticker} — {title} ({date_str})</option>\n'

    html = AB_TEST_TEMPLATE.format(
        document_options=document_options,
        results_html="",
    )
    return HTMLResponse(content=html)


@review_router.post("/ab-test", response_class=HTMLResponse)
async def run_ab_test(
    document_id: str = Form(),
    models: list[str] = Form(),
):
    """Run extraction comparison across selected models."""
    from src.config.company_registry import get_company_config
    from src.services.supabase_client import get_supabase_client
    from src.agents.universal_extractor import _build_extraction_request
    from src.agents.model_router import extract_with_model
    from src.models.universal_schemas import UniversalExtraction
    import httpx

    client = get_supabase_client()

    doc = client.table("company_documents").select("*").eq("id", document_id).limit(1).execute().data
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc = doc[0]

    company = client.table("companies").select("*").eq("id", doc["company_id"]).limit(1).execute().data
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    company = company[0]
    ticker = company["ticker"]

    config = get_company_config(ticker)
    if not config:
        raise HTTPException(status_code=400, detail=f"No config for {ticker}")

    companies_list = client.table("companies").select("id, ticker").execute().data
    co_map = {co["id"]: co["ticker"] for co in companies_list}

    # Get document content
    content = doc.get("raw_content", "")
    is_pdf = False
    if not content:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=60.0,
            headers={"User-Agent": "mREIT-Monitor/1.0 test@example.com"},
        ) as http_client:
            resp = await http_client.get(doc["source_url"])
            resp.raise_for_status()
            if "pdf" in resp.headers.get("content-type", "").lower():
                content = resp.content
                is_pdf = True
            else:
                content = resp.text

    system_prompt, user_content = _build_extraction_request(
        content, doc["document_type"], config, is_pdf
    )

    # Get baseline extraction for comparison
    baseline_ext = (
        client.table("universal_extractions")
        .select("*")
        .eq("document_id", document_id)
        .limit(1)
        .execute()
    ).data
    baseline = baseline_ext[0] if baseline_ext else None

    key_fields = [
        "book_value_per_share", "earnings_per_share", "dividends_per_share",
        "leverage_ratio", "portfolio_size", "agency_rmbs_holdings",
        "weighted_avg_coupon", "economic_return_pct",
    ]

    results = []
    for model in models:
        try:
            response_text, metadata = await extract_with_model(
                model=model,
                system_prompt=system_prompt,
                user_content=user_content,
                max_tokens=8192,
            )

            text = response_text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            data = json.loads(text)
            extraction = UniversalExtraction.model_validate(data)

            results.append({"model": model, "success": True, "extraction": extraction, "metadata": metadata})

            # Store comparison result
            try:
                client.table("extraction_comparisons").insert({
                    "document_id": document_id,
                    "model_name": model,
                    "extraction_data": extraction.model_dump(mode="json"),
                    "extraction_confidence": extraction.extraction_confidence,
                    "fields_extracted": len(extraction.fields_extracted),
                    "input_tokens": metadata.get("input_tokens", 0),
                    "output_tokens": metadata.get("output_tokens", 0),
                    "estimated_cost": metadata.get("estimated_cost", 0),
                    "latency_ms": metadata.get("latency_ms", 0),
                }).execute()
            except Exception as store_err:
                logger.warning("Failed to store comparison: %s", store_err)

        except Exception as e:
            logger.error("A/B test failed for %s: %s", model, e)
            results.append({"model": model, "success": False, "error": str(e)[:200], "metadata": {}})

    # Build results HTML
    results_cards = ""
    baseline_cost = None
    for r in results:
        if not r["success"]:
            results_cards += f"""
            <div class="result-card" style="border-color: #ffcdd2;">
                <h3>{r['model']}</h3>
                <div style="color: #c62828;">Failed: {r['error']}</div>
            </div>"""
            continue

        ext = r["extraction"]
        meta = r["metadata"]
        cost = meta.get("estimated_cost", 0)
        if baseline_cost is None:
            baseline_cost = cost

        metric_rows = ""
        for field in key_fields:
            val = getattr(ext, field, None)
            baseline_val = baseline.get(field) if baseline else None
            val_str = f"{val}" if val is not None else "—"
            css = ""
            if baseline_val is not None and val is not None:
                try:
                    match = abs(float(val) - float(baseline_val)) < 0.01 * max(abs(float(baseline_val)), 1)
                    css = "match" if match else "mismatch"
                except (ValueError, TypeError):
                    pass

            metric_rows += f"""
            <div class="metric-row">
                <span class="metric-label">{field}</span>
                <span class="metric-value {css}">{val_str}</span>
            </div>"""

        savings = ""
        if baseline_cost and baseline_cost > 0 and cost < baseline_cost:
            pct = (1 - cost / baseline_cost) * 100
            savings = f' <span class="cost-savings">({pct:.0f}% savings)</span>'

        results_cards += f"""
        <div class="result-card">
            <h3>{r['model']}</h3>
            <div class="meta">
                Confidence: {ext.extraction_confidence:.2f} |
                Fields: {len(ext.fields_extracted)} |
                Tokens: {meta.get('input_tokens', 0):,}+{meta.get('output_tokens', 0):,} |
                Latency: {meta.get('latency_ms', 0):,}ms
            </div>
            {metric_rows}
            <div class="cost">${cost:.4f}{savings}</div>
        </div>"""

    results_html = ""
    if results:
        results_html = f"""
        <div class="results">
            <h2 style="font-size: 18px;">Results — {ticker} {doc.get('title', '')}</h2>
            <p style="font-size: 13px; color: #666;">Baseline values from existing extraction (green = match, red = mismatch)</p>
            <div class="results-grid">{results_cards}</div>
        </div>"""

    # Rebuild page with results
    docs_list = (
        client.table("company_documents")
        .select("id, company_id, document_type, title, document_date, source_url")
        .eq("status", "completed")
        .order("document_date", desc=True)
        .limit(50)
        .execute()
    ).data

    document_options = ""
    for d in docs_list:
        t = co_map.get(d["company_id"], "?")
        title = d.get("title") or d.get("document_type", "?")
        date_str = (d.get("document_date") or "")[:10]
        selected = ' selected' if d["id"] == document_id else ''
        document_options += f'<option value="{d["id"]}"{selected}>{t} — {title} ({date_str})</option>\n'

    html = AB_TEST_TEMPLATE.format(
        document_options=document_options,
        results_html=results_html,
    )
    return HTMLResponse(content=html)
