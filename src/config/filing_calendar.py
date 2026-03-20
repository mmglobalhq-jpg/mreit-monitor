"""
Filing calendar — determines when to poll IR pages vs. just EDGAR.

EDGAR polling is free (no LLM cost), so it runs daily during filing windows
and weekly otherwise. IR page scraping uses an LLM, so it only runs during
the expected filing windows to minimize cost.

Windows are based on 2025 actual filing dates plus a buffer.
"""

from datetime import date
from typing import NamedTuple

# Companies that publish monthly updates (need mid-month IR scraping year-round)
MONTHLY_UPDATE_TICKERS = {"ARR", "ORC"}

# Companies that publish presentations/supplements on IR pages (need IR scraping during filing windows)
IR_SCRAPE_TICKERS = {"CIM", "AGNC", "NLY", "DX", "ARR", "ORC"}

# All tickers (EDGAR polling covers everyone)
ALL_TICKERS = {"ARR", "BMNM", "CIM", "AGNC", "NLY", "DX", "ORC"}


class FilingWindow(NamedTuple):
    """A date range during which filings are expected."""
    name: str
    start_month: int
    start_day: int
    end_month: int
    end_day: int


# Based on 2025 actual filing dates + ~1 week buffer on each side
FILING_WINDOWS = [
    FilingWindow("10-K Annual",   2,  1,  3, 15),  # Feb 1 – Mar 15
    FilingWindow("10-Q Q1",       4, 25,  5, 20),  # Apr 25 – May 20
    FilingWindow("10-Q Q2",       7, 25,  8, 20),  # Jul 25 – Aug 20
    FilingWindow("10-Q Q3",      10,  1, 11, 18),  # Oct 1 – Nov 18
]

# Monthly update window: 5th–22nd of each month
MONTHLY_UPDATE_START_DAY = 5
MONTHLY_UPDATE_END_DAY = 22


def _in_window(today: date, window: FilingWindow) -> bool:
    """Check if a date falls within a filing window."""
    start = date(today.year, window.start_month, window.start_day)
    end = date(today.year, window.end_month, window.end_day)
    return start <= today <= end


def is_filing_window(today: date | None = None) -> bool:
    """Return True if today is inside any quarterly/annual filing window."""
    today = today or date.today()
    return any(_in_window(today, w) for w in FILING_WINDOWS)


def is_monthly_update_window(today: date | None = None) -> bool:
    """Return True if today is in the mid-month update window (5th–22nd)."""
    today = today or date.today()
    return MONTHLY_UPDATE_START_DAY <= today.day <= MONTHLY_UPDATE_END_DAY


def get_active_filing_window(today: date | None = None) -> str | None:
    """Return the name of the active filing window, or None."""
    today = today or date.today()
    for w in FILING_WINDOWS:
        if _in_window(today, w):
            return w.name
    return None


def should_scrape_ir_pages(today: date | None = None) -> dict[str, list[str]]:
    """
    Determine which companies need IR page scraping today.

    Returns a dict with:
      - "filing_window": list of tickers to scrape (all IR_SCRAPE_TICKERS during filing windows)
      - "monthly_update": list of tickers to scrape (ARR, ORC during mid-month)
      - "none": empty list (no scraping needed)

    The caller should union these lists and deduplicate.
    """
    today = today or date.today()
    result: dict[str, list[str]] = {"filing_window": [], "monthly_update": []}

    # During filing windows: scrape all IR-relevant companies
    if is_filing_window(today):
        result["filing_window"] = sorted(IR_SCRAPE_TICKERS)

    # During monthly update windows (and NOT already in a filing window for these tickers):
    # scrape ARR and ORC for monthly portfolio PDFs
    if is_monthly_update_window(today):
        for ticker in MONTHLY_UPDATE_TICKERS:
            if ticker not in result["filing_window"]:
                result["monthly_update"].append(ticker)

    return result


def should_poll_edgar(today: date | None = None) -> tuple[bool, str]:
    """
    Determine if EDGAR should be polled today and at what frequency.

    Returns (should_poll, reason):
      - (True, "filing_window") — daily during filing windows
      - (True, "weekly_background") — Monday background check
      - (False, "off_peak") — no poll needed today
    """
    today = today or date.today()

    # Always poll during filing windows
    if is_filing_window(today):
        return True, "filing_window"

    # Weekly background check on Mondays
    if today.weekday() == 0:  # Monday
        return True, "weekly_background"

    return False, "off_peak"


def get_schedule_summary(today: date | None = None) -> str:
    """Human-readable summary of what's scheduled for today."""
    today = today or date.today()
    parts = []

    window = get_active_filing_window(today)
    if window:
        parts.append(f"Filing window: {window}")

    ir = should_scrape_ir_pages(today)
    all_ir = sorted(set(ir["filing_window"] + ir["monthly_update"]))
    if all_ir:
        parts.append(f"IR scrape: {', '.join(all_ir)}")
    else:
        parts.append("IR scrape: none")

    poll_edgar, reason = should_poll_edgar(today)
    parts.append(f"EDGAR: {'yes' if poll_edgar else 'no'} ({reason})")

    return " | ".join(parts)
