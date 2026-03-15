"""Shared parser utilities."""

import logging

from dateutil import parser as dateutil_parser

logger = logging.getLogger("mreit-monitor.parsers.utils")


def get_nested(data: dict | None, dotted_path: str):
    """Navigate a nested dict using a dotted path like 'key_metrics.stock_price'."""
    if data is None:
        return None
    keys = dotted_path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


def parse_date_string(date_str: str | None) -> str | None:
    """Parse date strings like '3/16/2026' or '12/31/2025' to ISO format."""
    if not date_str:
        return None
    try:
        parsed = dateutil_parser.parse(date_str)
        return parsed.date().isoformat()
    except (ValueError, TypeError):
        logger.warning("Could not parse date string: %s", date_str)
        return None
