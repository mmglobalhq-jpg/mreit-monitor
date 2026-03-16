"""
APScheduler setup for daily polling.

Runs inside the FastAPI lifespan context.
Polls company IR pages and SEC EDGAR for new filings once daily.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config.settings import settings

logger = logging.getLogger("mreit-monitor.scheduler")


async def poll_all_companies():
    """
    Main scheduled job: poll all active companies for new filings.

    Steps:
    1. Query the companies table for all active companies
    2. For each company, scrape their IR pages for new PDF/HTML links
    3. Poll SEC EDGAR for new filings
    4. For any new filings found, trigger the download + extraction pipeline
    """
    from src.config.companies import COMPANY_CONFIGS
    from src.config.company_registry import get_company_config
    from src.models.database import get_active_companies, get_latest_filing, log_poll
    from src.models.schemas import FilingType
    from src.services.edgar import check_new_filings as check_edgar_filings
    from src.services.scraper import DetectedFiling, scrape_company, filter_new_filings
    from src.parsers.monthly_update import process_monthly_update

    logger.info("Starting daily poll for all active companies...")

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

        # Get registry config for this company
        registry_config = get_company_config(ticker)

        try:
            # ----------------------------------------------------------
            # ARMOUR: Use existing scraper pipeline
            # Other companies: Use universal scraper
            # ----------------------------------------------------------
            if ticker == "ARR":
                # Existing ARMOUR pipeline (unchanged)
                detected = await scrape_company(company)
            elif registry_config:
                # Universal scraper for new companies
                from src.services.universal_scraper import (
                    scrape_company_universal,
                    filter_new_documents,
                )
                from src.parsers.universal_document_processor import process_document

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

                log_poll(company_id, "universal_scrape", ticker, new_filings=len(new_docs))

                for doc in new_docs:
                    try:
                        await process_document(
                            company_id=company_id,
                            company_name=company_name,
                            ticker=ticker,
                            company_config=registry_config,
                            source_url=doc.source_url,
                            document_type=doc.document_type,
                            document_date=doc.document_date,
                            period_label=doc.period_label,
                            title=doc.title,
                        )
                    except Exception as e:
                        logger.error(
                            "Failed to process %s %s %s: %s",
                            ticker, doc.document_type, doc.period_label, e,
                        )

                # Skip the ARMOUR-specific scraper/EDGAR/filter logic below
                detected = []
            else:
                logger.warning("No config for %s — skipping", ticker)
                continue

            # ----------------------------------------------------------
            # Phase 2: Poll SEC EDGAR (all companies)
            # ----------------------------------------------------------
            cik = registry_config.cik if registry_config else COMPANY_CONFIGS.get(ticker, {}).get("cik")

            if cik:
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

                config = COMPANY_CONFIGS.get(ticker, {})
                monthly_url = config.get("monthly_updates_url", "")
                log_poll(company_id, "ir_scrape", monthly_url, new_filings=len(new_filings))

                # ----------------------------------------------------------
                # Phase 4: Process each new filing
                # ----------------------------------------------------------
                for filing in new_filings:
                    filing_type_val = filing.filing_type.value
                    try:
                        if filing_type_val == "monthly_update":
                            await process_monthly_update(
                                company_id=company_id,
                                company_name=company_name,
                                ticker=ticker,
                                source_url=filing.source_url,
                                filing_date=filing.filing_date,
                                period_label=filing.period_label,
                            )
                        elif filing_type_val == "earnings_release":
                            # Process via universal pipeline for non-ARMOUR companies
                            if ticker != "ARR" and registry_config:
                                from src.parsers.universal_document_processor import process_document
                                await process_document(
                                    company_id=company_id,
                                    company_name=company_name,
                                    ticker=ticker,
                                    company_config=registry_config,
                                    source_url=filing.source_url,
                                    document_type="quarterly_earnings",
                                    document_date=filing.filing_date,
                                    period_label=filing.period_label,
                                )
                            else:
                                logger.info(
                                    "Detected earnings release for %s %s — skipping (use existing pipeline)",
                                    ticker, filing.period_label,
                                )
                        elif filing_type_val in ("quarterly_10q", "annual_10k"):
                            if ticker != "ARR" and registry_config:
                                from src.parsers.universal_document_processor import process_document
                                await process_document(
                                    company_id=company_id,
                                    company_name=company_name,
                                    ticker=ticker,
                                    company_config=registry_config,
                                    source_url=filing.source_url,
                                    document_type=filing_type_val,
                                    document_date=filing.filing_date,
                                    period_label=filing.period_label,
                                )
                            else:
                                logger.info(
                                    "Detected %s for %s %s — processing not yet implemented",
                                    filing_type_val, ticker, filing.period_label,
                                )
                        else:
                            logger.info(
                                "Skipping filing type %s for %s (%s)",
                                filing_type_val, ticker, filing.period_label,
                            )
                    except Exception as e:
                        logger.error(
                            "Failed to process %s %s %s: %s",
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
    """Create and start the scheduler with the daily poll job."""
    scheduler = AsyncIOScheduler()
    
    # Daily poll at configured time
    scheduler.add_job(
        poll_all_companies,
        CronTrigger(
            hour=settings.poll_hour,
            minute=settings.poll_minute,
            timezone=settings.poll_timezone,
        ),
        id="daily_poll",
        name="Daily mREIT filing poll",
        replace_existing=True,
    )
    
    # Summary report generation disabled — reports are now triggered manually
    # from the admin review page (human-in-the-loop workflow).
    # scheduler.add_job(
    #     generate_scheduled_summaries,
    #     CronTrigger(
    #         hour=10,
    #         minute=0,
    #         timezone=settings.poll_timezone,
    #     ),
    #     id="summary_generation",
    #     name="Summary report generation",
    #     replace_existing=True,
    # )

    scheduler.start()
    return scheduler


def shutdown_scheduler(scheduler: AsyncIOScheduler):
    """Gracefully shut down the scheduler."""
    scheduler.shutdown(wait=False)
    logger.info("Scheduler shut down.")
