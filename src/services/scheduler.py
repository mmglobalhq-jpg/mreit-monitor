"""
APScheduler setup for smart polling.

Runs inside the FastAPI lifespan context.
Uses the filing calendar to determine when to poll:
  - EDGAR (free): daily during filing windows, weekly on Mondays otherwise
  - IR pages (LLM cost): only during filing windows and monthly update windows

This reduces LLM costs by ~52% compared to daily-everything polling.
"""

import logging
from datetime import date as date_cls

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config.settings import settings
from src.config.filing_calendar import (
    should_poll_edgar,
    should_scrape_ir_pages,
    get_schedule_summary,
)

logger = logging.getLogger("mreit-monitor.scheduler")


async def poll_ir_pages_only():
    """
    Hourly job: scrape IR pages only — no EDGAR.
    Free since the switch to BS4 tier 1 / Qwen3 fallback.
    Skips if the filing calendar says no companies are due today.
    """
    from src.config.company_registry import get_company_config
    from src.models.database import get_active_companies, log_poll
    from src.services.universal_scraper import scrape_company_universal, filter_new_documents
    from src.parsers.universal_document_processor import store_detected_document

    today = date_cls.today()
    ir_plan = should_scrape_ir_pages(today)
    ir_tickers = set(ir_plan["filing_window"] + ir_plan["monthly_update"])

    if not ir_tickers:
        logger.debug("Hourly IR scrape: no companies due today — skipping")
        return

    logger.info("Hourly IR scrape starting — companies due: %s", sorted(ir_tickers))
    companies = get_active_companies()
    total_new = 0
    filing_details = []

    for company in companies:
        ticker = company["ticker"]
        company_id = company["id"]

        if ticker not in ir_tickers:
            continue

        registry_config = get_company_config(ticker)
        if not registry_config:
            logger.warning("No config for %s — skipping", ticker)
            continue

        try:
            universal_docs = await scrape_company_universal(registry_config, ticker)
            new_docs = await filter_new_documents(universal_docs, company_id)
            total_new += len(new_docs)

            for doc in new_docs:
                filing_details.append({
                    "ticker": ticker,
                    "type": doc.document_type,
                    "period": doc.period_label or "",
                    "url": doc.source_url,
                })
                try:
                    store_detected_document(
                        company_id=company_id,
                        ticker=ticker,
                        source_url=doc.source_url,
                        document_type=doc.document_type,
                        document_date=doc.document_date,
                        title=doc.title,
                        period_label=doc.period_label or "",
                    )
                except Exception as e:
                    logger.error(
                        "Failed to store detected %s %s %s: %s",
                        ticker, doc.document_type, doc.period_label, e,
                    )

            log_poll(company_id, "universal_scrape", ticker, new_filings=len(new_docs))

        except Exception as e:
            logger.error("IR scrape failed for %s: %s", ticker, e)
            try:
                log_poll(company_id, "ir_scrape", "", error=str(e)[:500])
            except Exception:
                pass

    logger.info("Hourly IR scrape complete. New documents: %d", total_new)
    if total_new > 0:
        await send_new_filing_notification(total_new, filing_details)


async def poll_edgar_only():
    """
    Daily job: poll SEC EDGAR only — no IR scrape.
    Free. Respects the filing calendar (daily in windows, weekly on Mondays otherwise).
    """
    from src.config.company_registry import get_company_config
    from src.models.database import get_active_companies, get_latest_filing, log_poll, filter_new_filings
    from src.models.schemas import FilingType, DetectedFiling
    from src.services.edgar import check_new_filings as check_edgar_filings
    from src.parsers.universal_document_processor import store_detected_document

    today = date_cls.today()
    poll_edgar, edgar_reason = should_poll_edgar(today)

    if not poll_edgar:
        logger.info("Daily EDGAR check: off-peak day — skipping (%s)", edgar_reason)
        return

    logger.info("Daily EDGAR check starting (%s)", edgar_reason)
    companies = get_active_companies()
    total_new = 0
    filing_details = []

    _FORM_TYPE_MAP = {
        "10-Q": FilingType.QUARTERLY_10Q,
        "10-Q/A": FilingType.QUARTERLY_10Q,
        "10-K": FilingType.ANNUAL_10K,
        "10-K/A": FilingType.ANNUAL_10K,
        "8-K": FilingType.OTHER,
    }
    _DOC_TYPE_MAP = {
        "earnings_release": "quarterly_earnings",
        "quarterly_10q": "quarterly_10q",
        "annual_10k": "annual_10k",
        "monthly_update": "monthly_update",
    }

    for company in companies:
        ticker = company["ticker"]
        company_id = company["id"]
        registry_config = get_company_config(ticker)
        if not registry_config:
            logger.warning("No config for %s — skipping", ticker)
            continue

        cik = registry_config.cik
        if not cik:
            logger.debug("No CIK for %s — skipping EDGAR", ticker)
            continue

        try:
            latest_filing = get_latest_filing(company_id)
            last_poll_date = None
            if latest_filing and latest_filing.get("filing_date"):
                from datetime import datetime as datetime_cls
                raw = latest_filing["filing_date"]
                if isinstance(raw, str):
                    last_poll_date = datetime_cls.strptime(raw[:10], "%Y-%m-%d").date()
                elif isinstance(raw, date_cls):
                    last_poll_date = raw

            if last_poll_date is None:
                from datetime import timedelta
                last_poll_date = date_cls.today() - timedelta(days=90)
                logger.info("No prior filings for %s — defaulting to 90-day lookback", ticker)

            edgar_filings = await check_edgar_filings(cik, since_date=last_poll_date)
            detected = []

            for ef in edgar_filings:
                filing_type = _FORM_TYPE_MAP.get(ef.form_type, FilingType.OTHER)
                period_label = f"{ef.form_type} {ef.filing_date.isoformat()}"
                detected.append(DetectedFiling(
                    source_url=ef.primary_document_url,
                    filing_type=filing_type,
                    filing_date=ef.filing_date,
                    period_label=period_label,
                    source_page=f"edgar:{cik}",
                ))

            logger.info(
                "EDGAR check %s (CIK %s): %d filings found",
                ticker, cik, len(edgar_filings),
            )
            log_poll(company_id, "edgar", f"CIK:{cik}", new_filings=len(edgar_filings))

            if detected:
                new_filings = await filter_new_filings(detected, company_id)
                total_new += len(new_filings)

                for filing in new_filings:
                    filing_details.append({
                        "ticker": ticker,
                        "type": filing.filing_type.value,
                        "period": filing.period_label or "",
                        "url": filing.source_url,
                    })
                    filing_type_val = filing.filing_type.value
                    if filing_type_val in _DOC_TYPE_MAP:
                        try:
                            store_detected_document(
                                company_id=company_id,
                                ticker=ticker,
                                source_url=filing.source_url,
                                document_type=_DOC_TYPE_MAP[filing_type_val],
                                document_date=filing.filing_date,
                                title=f"{ticker} {filing.period_label}",
                                period_label=filing.period_label or "",
                            )
                        except Exception as e:
                            logger.error(
                                "Failed to store detected %s %s %s: %s",
                                ticker, filing_type_val, filing.period_label, e,
                            )

                log_poll(company_id, "edgar", f"CIK:{cik}", new_filings=len(new_filings))

        except Exception as e:
            logger.error("EDGAR check failed for %s (CIK %s): %s", ticker, cik, e)
            try:
                log_poll(company_id, "edgar", f"CIK:{cik}", error=str(e)[:500])
            except Exception:
                pass

    logger.info("Daily EDGAR check complete. New filings: %d", total_new)
    if total_new > 0:
        await send_new_filing_notification(total_new, filing_details)


async def poll_all_companies():
    """
    Main scheduled job: smart polling based on filing calendar.

    Checks the filing calendar to decide:
    1. Whether to poll EDGAR today (free — daily in windows, weekly otherwise)
    2. Which companies need IR page scraping today (costs LLM tokens)
    3. Skips entirely on off-peak days that aren't Mondays
    """
    from src.config.company_registry import get_company_config
    from src.models.database import get_active_companies, get_latest_filing, log_poll, filter_new_filings
    from src.models.schemas import FilingType, DetectedFiling
    from src.services.edgar import check_new_filings as check_edgar_filings
    from src.services.universal_scraper import scrape_company_universal, filter_new_documents
    from src.parsers.universal_document_processor import store_detected_document

    today = date_cls.today()
    schedule = get_schedule_summary(today)
    logger.info("Daily poll check — %s", schedule)

    poll_edgar, edgar_reason = should_poll_edgar(today)
    ir_plan = should_scrape_ir_pages(today)
    ir_tickers = set(ir_plan["filing_window"] + ir_plan["monthly_update"])

    if not poll_edgar and not ir_tickers:
        logger.info("Off-peak day — skipping all polling")
        return

    logger.info(
        "Starting poll: EDGAR=%s (%s), IR scrape=%s",
        poll_edgar, edgar_reason, sorted(ir_tickers) if ir_tickers else "none",
    )

    companies = get_active_companies()
    if not companies:
        logger.warning("No active companies found — nothing to poll")
        return

    # Map EDGAR form types to our FilingType enum
    _FORM_TYPE_MAP = {
        "10-Q": FilingType.QUARTERLY_10Q,
        "10-Q/A": FilingType.QUARTERLY_10Q,
        "10-K": FilingType.ANNUAL_10K,
        "10-K/A": FilingType.ANNUAL_10K,
        "8-K": FilingType.OTHER,
    }

    total_new = 0
    filing_details = []

    for company in companies:
        ticker = company["ticker"]
        company_id = company["id"]
        company_name = company["name"]

        registry_config = get_company_config(ticker)
        if not registry_config:
            logger.warning("No config for %s — skipping", ticker)
            continue

        try:
            # ----------------------------------------------------------
            # Phase 1: Universal scraper (only during active windows)
            # ----------------------------------------------------------
            new_docs = []
            if ticker in ir_tickers:
                universal_docs = await scrape_company_universal(registry_config, ticker)
                new_docs = await filter_new_documents(universal_docs, company_id)
            else:
                logger.debug("Skipping IR scrape for %s (not in today's window)", ticker)
            total_new += len(new_docs)
            for doc in new_docs:
                filing_details.append({
                    "ticker": ticker,
                    "type": doc.document_type,
                    "period": doc.period_label or "",
                    "url": doc.source_url,
                })

            log_poll(company_id, "universal_scrape", ticker, new_filings=len(new_docs))

            # Store as detected — user approves processing from Review page
            for doc in new_docs:
                try:
                    store_detected_document(
                        company_id=company_id,
                        ticker=ticker,
                        source_url=doc.source_url,
                        document_type=doc.document_type,
                        document_date=doc.document_date,
                        title=doc.title,
                        period_label=doc.period_label or "",
                    )
                except Exception as e:
                    logger.error(
                        "Failed to store detected %s %s %s: %s",
                        ticker, doc.document_type, doc.period_label, e,
                    )

            # ----------------------------------------------------------
            # Phase 2: Poll SEC EDGAR (free — runs when calendar says to)
            # ----------------------------------------------------------
            detected = []
            cik = registry_config.cik

            if not poll_edgar:
                logger.debug("Skipping EDGAR poll for %s (off-peak, not Monday)", ticker)
            elif cik:
                try:
                    latest_filing = get_latest_filing(company_id)
                    last_poll_date = None
                    if latest_filing and latest_filing.get("filing_date"):
                        from datetime import date as date_cls, datetime as datetime_cls
                        raw = latest_filing["filing_date"]
                        if isinstance(raw, str):
                            last_poll_date = datetime_cls.strptime(raw[:10], "%Y-%m-%d").date()
                        elif isinstance(raw, date_cls):
                            last_poll_date = raw

                    # Default to 90 days lookback to avoid processing entire filing history
                    if last_poll_date is None:
                        from datetime import date as date_cls, timedelta
                        last_poll_date = date_cls.today() - timedelta(days=90)
                        logger.info("No prior filings for %s — defaulting to 90-day lookback", ticker)

                    edgar_filings = await check_edgar_filings(cik, since_date=last_poll_date)

                    for ef in edgar_filings:
                        filing_type = _FORM_TYPE_MAP.get(ef.form_type, FilingType.OTHER)
                        period_label = f"{ef.form_type} {ef.filing_date.isoformat()}"
                        detected.append(DetectedFiling(
                            source_url=ef.primary_document_url,
                            filing_type=filing_type,
                            filing_date=ef.filing_date,
                            period_label=period_label,
                            source_page=f"edgar:{cik}",
                        ))

                    logger.info(
                        "EDGAR poll for %s (CIK %s): %d relevant filings found",
                        ticker, cik, len(edgar_filings),
                    )
                    log_poll(company_id, "edgar", f"CIK:{cik}", new_filings=len(edgar_filings))
                except Exception as e:
                    logger.error("EDGAR poll failed for %s (CIK %s): %s", ticker, cik, e)
                    try:
                        log_poll(company_id, "edgar", f"CIK:{cik}", error=str(e)[:500])
                    except Exception:
                        pass

            # ----------------------------------------------------------
            # Phase 3: Filter to only new filings (dedup against DB)
            # ----------------------------------------------------------
            if detected:
                new_filings = await filter_new_filings(detected, company_id)
                total_new += len(new_filings)
                for filing in new_filings:
                    filing_details.append({
                        "ticker": ticker,
                        "type": filing.filing_type.value,
                        "period": filing.period_label or "",
                        "url": filing.source_url,
                    })

                log_poll(company_id, "edgar", f"CIK:{cik}", new_filings=len(new_filings))

                # ----------------------------------------------------------
                # Phase 4: Store detected EDGAR filings (detect-only)
                # ----------------------------------------------------------
                _DOC_TYPE_MAP = {
                    "earnings_release": "quarterly_earnings",
                    "quarterly_10q": "quarterly_10q",
                    "annual_10k": "annual_10k",
                    "monthly_update": "monthly_update",
                }

                for filing in new_filings:
                    filing_type_val = filing.filing_type.value
                    try:
                        if filing_type_val in _DOC_TYPE_MAP:
                            store_detected_document(
                                company_id=company_id,
                                ticker=ticker,
                                source_url=filing.source_url,
                                document_type=_DOC_TYPE_MAP[filing_type_val],
                                document_date=filing.filing_date,
                                title=f"{ticker} {filing.period_label}",
                                period_label=filing.period_label or "",
                            )
                        else:
                            logger.info(
                                "Skipping filing type %s for %s (%s)",
                                filing_type_val, ticker, filing.period_label,
                            )
                    except Exception as e:
                        logger.error(
                            "Failed to store detected %s %s %s: %s",
                            ticker, filing_type_val, filing.period_label, e,
                        )

        except Exception as e:
            logger.error("Failed to poll %s: %s", ticker, e)
            try:
                log_poll(company_id, "ir_scrape", "", error=str(e)[:500])
            except Exception:
                pass

    logger.info("Daily poll complete. Total new filings processed: %d", total_new)

    # Send notification email if new filings were found
    if total_new > 0:
        await send_new_filing_notification(total_new, filing_details)


async def generate_scheduled_summaries():
    """
    Generate summary reports for all active companies.
    Called by cron jobs on monthly/quarterly/annual schedules.
    """
    from datetime import date as date_cls
    from src.models.database import get_active_companies
    from src.services.summary_service import (
        generate_monthly_summary,
        generate_quarterly_summary,
        generate_annual_summary,
    )

    if not settings.summary_enabled:
        logger.info("Summary generation disabled (SUMMARY_ENABLED=false), skipping")
        return

    today = date_cls.today()
    companies = get_active_companies()

    from src.config.company_registry import get_company_config

    # Companies that have monthly updates (and thus monthly summaries)
    MONTHLY_SUMMARY_TICKERS = {"ARR"}
    # Companies with optional lightweight monthly notes
    OPTIONAL_MONTHLY_TICKERS = {"AGNC", "DX"}

    for company in companies:
        company_id = company["id"]
        company_name = company["name"]
        ticker = company["ticker"]

        try:
            # Monthly summary: run on the 5th, for the prior month
            # Only for companies with monthly data (ARR)
            if today.day == 5 and ticker in MONTHLY_SUMMARY_TICKERS:
                if today.month == 1:
                    await generate_monthly_summary(company_id, company_name, ticker, today.year - 1, 12)
                else:
                    await generate_monthly_summary(company_id, company_name, ticker, today.year, today.month - 1)

            # Quarterly summary: ~35 days after quarter-end (Feb 4, May 5, Aug 4, Nov 4)
            # All companies get quarterly summaries
            quarter_map = {2: (4, today.year - 1), 5: (1, today.year), 8: (2, today.year), 11: (3, today.year)}
            if today.month in quarter_map and today.day in (4, 5):
                quarter, year = quarter_map[today.month]
                await generate_quarterly_summary(company_id, company_name, ticker, year, quarter)

            # Annual summary: March 1st for the prior year
            if today.month == 3 and today.day == 1:
                await generate_annual_summary(company_id, company_name, ticker, today.year - 1)

        except Exception as e:
            logger.error("Failed to generate summary for %s: %s", ticker, e)


async def send_new_filing_notification(total_new: int, filing_details: list[dict]):
    """
    Send an email to the admin when new filings are detected during the daily poll.
    Only called when total_new > 0.
    """
    import resend
    from datetime import datetime

    resend.api_key = settings.resend_api_key

    # Build filing list HTML
    rows = ""
    for f in filing_details:
        rows += f'<tr><td>{f["ticker"]}</td><td>{f["type"]}</td><td>{f["period"]}</td><td><a href="{f["url"]}">{f["url"][:60]}...</a></td></tr>'

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .container {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 24px; }}
        h1 {{ font-size: 18px; margin: 0 0 16px; color: #1a1a1a; }}
        table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
        th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 13px; }}
        th {{ color: #888; font-weight: 600; }}
        a {{ color: #BA0C2F; }}
        .button {{ display: inline-block; padding: 12px 28px; background: #1a1a1a; color: #fff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 14px; margin-top: 16px; }}
        .footer {{ margin-top: 20px; font-size: 12px; color: #999; }}
    </style></head>
    <body>
        <div class="container">
            <h1>New REIT Filings Detected</h1>
            <p>{total_new} new filing(s) found during the daily poll at {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}.</p>
            <table>
                <tr><th>Ticker</th><th>Type</th><th>Period</th><th>Source</th></tr>
                {rows}
            </table>
            <a href="https://mmglobal.us/reit-monitor/review" class="button">Review Filings</a>
            <div class="footer">This is an automated notification from mREIT Monitor.</div>
        </div>
    </body>
    </html>
    """

    try:
        result = resend.Emails.send({
            "from": settings.alert_email_from,
            "to": [settings.alert_email_to],
            "subject": f"[mREIT Monitor] {total_new} new filing(s) detected",
            "html": html,
        })
        logger.info("New-filing notification sent (id: %s)", result.get("id"))
    except Exception as e:
        logger.error("Failed to send new-filing notification: %s", e)


def start_scheduler() -> AsyncIOScheduler:
    """Create and start the scheduler with two jobs: hourly IR scrape + daily EDGAR check."""
    scheduler = AsyncIOScheduler()

    # Hourly IR page scrape — market hours Mon-Fri, top of each hour
    scheduler.add_job(
        poll_ir_pages_only,
        CronTrigger(
            hour="6-20",
            day_of_week="mon-fri",
            timezone="US/Eastern",
        ),
        id="hourly_ir_scrape",
        name="Hourly mREIT IR page scrape",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Daily EDGAR check at configured time
    scheduler.add_job(
        poll_edgar_only,
        CronTrigger(
            hour=settings.poll_hour,
            minute=settings.poll_minute,
            timezone=settings.poll_timezone,
        ),
        id="daily_edgar",
        name="Daily EDGAR filing check",
        replace_existing=True,
    )

    scheduler.start()
    return scheduler


def shutdown_scheduler(scheduler: AsyncIOScheduler):
    """Gracefully shut down the scheduler."""
    scheduler.shutdown(wait=False)
    logger.info("Scheduler shut down.")
