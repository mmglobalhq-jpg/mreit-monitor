"""
Email alert service — sends processing notifications via Resend.
"""

import logging

import resend

from src.config.settings import settings
from src.agents.prompts.templates import EMAIL_SUBJECT_TEMPLATE, EMAIL_BODY_TEMPLATE
from src.models.schemas import ComparisonAnalysis

logger = logging.getLogger("mreit-monitor.email")


def init_resend():
    """Initialize the Resend client."""
    resend.api_key = settings.resend_api_key


async def send_filing_alert(
    ticker: str,
    company_name: str,
    filing_type_label: str,
    period_label: str,
    source_url: str,
    analysis: ComparisonAnalysis | None = None,
    metrics_summary: list[dict] | None = None,
) -> bool:
    """
    Send an email alert for a processed filing.
    
    Args:
        ticker: Company ticker
        company_name: Full company name
        filing_type_label: Human-readable filing type (e.g., "Monthly Update")
        period_label: Period label (e.g., "March 2026")
        source_url: Original filing URL
        analysis: Comparison analysis results (if available)
        metrics_summary: Key metrics with current/prior/delta (for the table)
        
    Returns:
        True if email sent successfully
    """
    init_resend()
    
    subject = EMAIL_SUBJECT_TEMPLATE.format(
        ticker=ticker,
        period_label=period_label,
        filing_type_label=filing_type_label,
    )
    
    # Build metrics rows HTML
    metrics_rows = ""
    if metrics_summary:
        for m in metrics_summary:
            direction_class = m.get("direction", "flat")
            delta_str = m.get("delta_str", "—")
            metrics_rows += f"""
            <tr>
                <td>{m['name']}</td>
                <td>{m.get('current', '—')}</td>
                <td>{m.get('prior', '—')}</td>
                <td class="{direction_class}">{delta_str}</td>
            </tr>"""
    
    # Build anomalies section
    anomalies_section = ""
    if analysis and analysis.anomalies:
        anomalies_section = "<h2>Anomalies</h2>"
        for a in analysis.anomalies:
            css_class = "anomaly high" if a.severity == "high" else "anomaly"
            anomalies_section += f'<div class="{css_class}"><strong>{a.metric}:</strong> {a.description}</div>'
    
    # Build analysis content
    analysis_content = ""
    if analysis:
        analysis_content = analysis.full_analysis
    
    # Build portfolio shifts section
    portfolio_shifts_section = ""
    if analysis and analysis.portfolio_shifts:
        portfolio_shifts_section = '<table class="metrics-table"><tr><th>Coupon</th><th>Prior %</th><th>Current %</th><th>Change</th></tr>'
        for ps in analysis.portfolio_shifts:
            portfolio_shifts_section += f"<tr><td>{ps.coupon}</td><td>{ps.prior_pct or '—'}</td><td>{ps.current_pct or '—'}</td><td>{ps.change_pct or '—'}</td></tr>"
        portfolio_shifts_section += "</table>"
    
    from datetime import datetime
    
    body = EMAIL_BODY_TEMPLATE.format(
        company_name=company_name,
        ticker=ticker,
        filing_type_label=filing_type_label,
        period_label=period_label,
        processed_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        metrics_rows=metrics_rows,
        anomalies_section=anomalies_section,
        analysis_content=analysis_content,
        portfolio_shifts_section=portfolio_shifts_section,
        source_url=source_url,
    )
    
    try:
        result = resend.Emails.send({
            "from": settings.alert_email_from,
            "to": [settings.alert_email_to],
            "subject": subject,
            "html": body,
        })
        logger.info("Email alert sent for %s %s (id: %s)", ticker, period_label, result.get("id"))
        return True
    except Exception as e:
        logger.error("Failed to send email alert: %s", str(e))
        return False
