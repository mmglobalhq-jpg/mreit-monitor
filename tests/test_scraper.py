"""
Tests for the IR page scraper — helper functions and filter logic.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from src.services.scraper import (
    DetectedFiling,
    _extract_date_from_context,
    _extract_period_from_title,
    filter_new_filings,
)
from src.models.schemas import FilingType


# ============================================================================
# _extract_period_from_title
# ============================================================================


class TestExtractPeriodFromTitle:
    def test_standard_monthly_update_title(self):
        result = _extract_period_from_title("March 2026 Company Update (1).pdf")
        assert result == "March 2026"

    def test_quarterly_title(self):
        result = _extract_period_from_title("ARR Q4 2025.pdf")
        # No "Month Year" pattern; no YYYY-MM pattern; returns None
        assert result is None

    def test_month_year_only(self):
        result = _extract_period_from_title("January 2025 Update.pdf")
        assert result == "January 2025"

    def test_yyyy_mm_pattern(self):
        result = _extract_period_from_title("report-2025-06-data.pdf")
        assert result == "June 2025"

    def test_empty_string(self):
        result = _extract_period_from_title("")
        assert result is None

    def test_none_input(self):
        result = _extract_period_from_title(None)
        assert result is None

    def test_no_date_information(self):
        result = _extract_period_from_title("random-document.pdf")
        assert result is None

    def test_all_months(self):
        months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
        for month in months:
            result = _extract_period_from_title(f"{month} 2025 Company Update.pdf")
            assert result == f"{month} 2025", f"Failed for {month}"


# ============================================================================
# _extract_date_from_context
# ============================================================================


class TestExtractDateFromContext:
    def _make_link(self, html: str) -> BeautifulSoup:
        """Parse HTML and return the first <a> element."""
        soup = BeautifulSoup(html, "lxml")
        return soup.find("a")

    def test_date_in_parent_text(self):
        html = '<div>3/13/2026 <a href="/static-files/abc123" title="March 2026 Update.pdf">Link</a></div>'
        link = self._make_link(html)
        result = _extract_date_from_context(link)
        assert result == date(2026, 3, 13)

    def test_date_in_previous_sibling(self):
        html = '<div><span>1/15/2025</span><a href="/test">Link</a></div>'
        link = self._make_link(html)
        result = _extract_date_from_context(link)
        # Should find the date in parent text or sibling
        assert result == date(2025, 1, 15)

    def test_date_from_title_attribute_fallback(self):
        html = '<div><a href="/test" title="February 2025 Update.pdf">Link</a></div>'
        link = self._make_link(html)
        result = _extract_date_from_context(link)
        # Fallback: derives date from Month YYYY in title → first of month
        assert result == date(2025, 2, 1)

    def test_no_date_found(self):
        html = '<div><a href="/test">No date here</a></div>'
        link = self._make_link(html)
        result = _extract_date_from_context(link)
        assert result is None

    def test_date_in_grandparent(self):
        html = '<section><div>12/31/2025</div><div><a href="/test">Link</a></div></section>'
        link = self._make_link(html)
        result = _extract_date_from_context(link)
        # grandparent strategy should find the date
        assert result == date(2025, 12, 31)


# ============================================================================
# filter_new_filings
# ============================================================================


class TestFilterNewFilings:
    @pytest.fixture
    def sample_filings(self):
        return [
            DetectedFiling(
                source_url="https://example.com/file1.pdf",
                filing_type=FilingType.MONTHLY_UPDATE,
                filing_date=date(2026, 3, 13),
                period_label="March 2026",
                source_page="https://example.com/updates",
            ),
            DetectedFiling(
                source_url="https://example.com/file2.pdf",
                filing_type=FilingType.MONTHLY_UPDATE,
                filing_date=date(2026, 2, 18),
                period_label="February 2026",
                source_page="https://example.com/updates",
            ),
            DetectedFiling(
                source_url="https://example.com/file3.pdf",
                filing_type=FilingType.EARNINGS_RELEASE,
                filing_date=date(2025, 10, 22),
                period_label="Q3 2025",
                source_page="https://example.com/quarterly",
            ),
        ]

    @pytest.mark.asyncio
    async def test_filters_existing_urls(self, sample_filings):
        """Filings whose source_url already exists in the DB are excluded."""
        mock_response = MagicMock()
        mock_response.data = [
            {"source_url": "https://example.com/file1.pdf"},
            {"source_url": "https://example.com/file3.pdf"},
        ]

        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.execute.return_value = mock_response

        mock_client = MagicMock()
        mock_client.table.return_value = mock_table

        with patch("src.services.supabase_client.get_supabase_client", return_value=mock_client):
            result = await filter_new_filings(sample_filings, "company-uuid-1")

        assert len(result) == 1
        assert result[0].source_url == "https://example.com/file2.pdf"

    @pytest.mark.asyncio
    async def test_all_new(self, sample_filings):
        """When nothing exists in the DB, all filings are returned."""
        mock_response = MagicMock()
        mock_response.data = []

        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.execute.return_value = mock_response

        mock_client = MagicMock()
        mock_client.table.return_value = mock_table

        with patch("src.services.supabase_client.get_supabase_client", return_value=mock_client):
            result = await filter_new_filings(sample_filings, "company-uuid-1")

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_all_existing(self, sample_filings):
        """When all URLs exist in the DB, empty list is returned."""
        mock_response = MagicMock()
        mock_response.data = [{"source_url": f.source_url} for f in sample_filings]

        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.execute.return_value = mock_response

        mock_client = MagicMock()
        mock_client.table.return_value = mock_table

        with patch("src.services.supabase_client.get_supabase_client", return_value=mock_client):
            result = await filter_new_filings(sample_filings, "company-uuid-1")

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_empty_detected_list(self):
        """An empty detected list returns an empty result."""
        mock_response = MagicMock()
        mock_response.data = []

        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.execute.return_value = mock_response

        mock_client = MagicMock()
        mock_client.table.return_value = mock_table

        with patch("src.services.supabase_client.get_supabase_client", return_value=mock_client):
            result = await filter_new_filings([], "company-uuid-1")

        assert result == []
