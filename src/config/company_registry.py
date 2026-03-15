"""
Multi-company registry — defines reporting profiles for all monitored mREITs.

Each company entry specifies what documents it publishes, where to find them,
and how frequently to check. This drives the universal scraper and extraction pipeline.

The existing companies.py (ARMOUR-specific config + backfill URLs) is NOT modified.
"""

from dataclasses import dataclass, field


@dataclass
class ScrapeSource:
    """A single source to check for new documents."""
    type: str  # "website" or "edgar"
    url: str = ""
    doc_type: str = ""  # document type this source yields
    filing_types: list[str] = field(default_factory=list)  # for EDGAR sources


@dataclass
class CompanyConfig:
    """Full configuration for a monitored mREIT."""
    name: str
    cik: str
    document_types: list[str]
    scrape_sources: list[ScrapeSource]
    primary_focus: list[str]
    has_monthly_update: bool = False
    has_financial_supplement: bool = False
    has_investor_presentation: bool = False
    notes: str = ""
    check_cadence: str = "weekly"


COMPANY_REGISTRY: dict[str, CompanyConfig] = {
    "ARR": CompanyConfig(
        name="ARMOUR Residential REIT",
        cik="0001428205",
        document_types=["monthly_update", "quarterly_earnings", "sec_filing"],
        scrape_sources=[
            ScrapeSource(type="website", url="https://www.armourreit.com/news-events/monthly-company-updates", doc_type="monthly_update"),
            ScrapeSource(type="website", url="https://www.armourreit.com/financials/quarterly-reports", doc_type="quarterly_earnings"),
            ScrapeSource(type="website", url="https://www.armourreit.com/news-events/news", doc_type="press_release"),
            ScrapeSource(type="edgar", filing_types=["10-Q", "10-K", "8-K"]),
        ],
        primary_focus=["agency_rmbs"],
        has_monthly_update=True,
        has_financial_supplement=False,
        has_investor_presentation=False,
        notes="Pure Agency RMBS. Monthly PDF is the primary data source with detailed portfolio, repo, swap, and hedge data.",
        check_cadence="weekly",
    ),
    "BMNM": CompanyConfig(
        name="Bimini Capital Management",
        cik="0001275477",
        document_types=["quarterly_earnings", "sec_filing"],
        scrape_sources=[
            ScrapeSource(type="website", url="https://www.biminicapital.com/financials/quarterly-results", doc_type="quarterly_earnings"),
            ScrapeSource(type="website", url="https://www.biminicapital.com/news", doc_type="press_release"),
            ScrapeSource(type="edgar", filing_types=["10-Q", "10-K", "8-K"]),
        ],
        primary_focus=["agency_rmbs", "advisory_services"],
        has_monthly_update=False,
        has_financial_supplement=False,
        has_investor_presentation=False,
        notes="Two segments: MBS portfolio + advisory services (manages Orchid Island Capital). Smallest company in group. Press release is primary data source.",
        check_cadence="weekly",
    ),
    "CIM": CompanyConfig(
        name="Chimera Investment Corporation",
        cik="0001409493",
        document_types=["quarterly_earnings", "financial_supplement", "investor_presentation", "sec_filing"],
        scrape_sources=[
            ScrapeSource(type="website", url="https://www.chimerareit.com/financial-information/financial-results", doc_type="quarterly_earnings"),
            ScrapeSource(type="website", url="https://www.chimerareit.com/news-events/press-releases", doc_type="press_release"),
            ScrapeSource(type="edgar", filing_types=["10-Q", "10-K", "8-K"]),
        ],
        primary_focus=["agency_rmbs", "non_agency_rmbs", "residential_loans", "msr", "cmbs", "origination"],
        has_monthly_update=False,
        has_financial_supplement=True,
        has_investor_presentation=True,
        notes="Hybrid REIT. Separate financial supplement from press release. HomeXpress origination data. Multiple asset classes.",
        check_cadence="weekly",
    ),
    "AGNC": CompanyConfig(
        name="AGNC Investment Corp",
        cik="0001423689",
        document_types=["quarterly_earnings", "monthly_book_value", "investor_presentation", "sec_filing"],
        scrape_sources=[
            ScrapeSource(type="website", url="https://investors.agnc.com/financial-information/quarterly-results", doc_type="quarterly_earnings"),
            ScrapeSource(type="website", url="https://investors.agnc.com/events-and-presentations/upcoming-events", doc_type="investor_presentation"),
            ScrapeSource(type="edgar", filing_types=["10-Q", "10-K", "8-K"]),
        ],
        primary_focus=["agency_rmbs", "tba_securities"],
        has_monthly_update=False,
        has_financial_supplement=False,
        has_investor_presentation=True,
        notes="Earnings press release IS the supplement (20+ pages of tables). Monthly BV estimate press releases. Largest pure Agency REIT ($94.8B portfolio).",
        check_cadence="weekly",
    ),
    "NLY": CompanyConfig(
        name="Annaly Capital Management",
        cik="0001043219",
        document_types=["quarterly_earnings", "financial_supplement", "investor_presentation", "sec_filing"],
        scrape_sources=[
            ScrapeSource(type="website", url="https://www.annaly.com/investors/earnings-and-financials/quarterly-earnings", doc_type="quarterly_earnings"),
            ScrapeSource(type="website", url="https://www.annaly.com/investors/earnings-and-financials/presentations/2026", doc_type="investor_presentation"),
            ScrapeSource(type="edgar", filing_types=["10-Q", "10-K", "8-K"]),
        ],
        primary_focus=["agency_rmbs", "residential_credit", "msr"],
        has_monthly_update=False,
        has_financial_supplement=True,
        has_investor_presentation=True,
        notes="Three segments: Agency, Residential Credit, MSR. Three docs per quarter: press release, supplement, presentation. Largest mREIT overall (~$132B). PAA is key non-GAAP metric.",
        check_cadence="weekly",
    ),
    "DX": CompanyConfig(
        name="Dynex Capital",
        cik="0000826675",
        document_types=["quarterly_earnings", "investor_presentation", "monthly_dividend", "sec_filing"],
        scrape_sources=[
            ScrapeSource(type="website", url="https://www.dynexcapital.com/investors/financial-info/financial-results", doc_type="quarterly_earnings"),
            ScrapeSource(type="website", url="https://www.dynexcapital.com/investors/news-events/press-releases", doc_type="press_release"),
            ScrapeSource(type="website", url="https://www.dynexcapital.com/investors/news-events/presentations", doc_type="investor_presentation"),
            ScrapeSource(type="edgar", filing_types=["10-Q", "10-K", "8-K"]),
        ],
        primary_focus=["agency_rmbs", "agency_cmbs"],
        has_monthly_update=False,
        has_financial_supplement=False,
        has_investor_presentation=True,
        notes="Monthly dividend press releases may include market commentary and BV estimates. Both RMBS and CMBS. Rich quarterly presentations with market analysis.",
        check_cadence="weekly",
    ),
    "ORC": CompanyConfig(
        name="Orchid Island Capital",
        cik="0001518621",
        document_types=["quarterly_earnings", "monthly_update", "sec_filing"],
        scrape_sources=[
            ScrapeSource(type="website", url="https://www.orchidislandcapital.com/financial-information/quarterly-results", doc_type="quarterly_earnings"),
            ScrapeSource(type="website", url="https://www.orchidislandcapital.com/financial-information/monthly-portfolio-characteristics", doc_type="monthly_update"),
            ScrapeSource(type="website", url="https://www.orchidislandcapital.com/news-events/press-releases", doc_type="press_release"),
            ScrapeSource(type="edgar", filing_types=["10-Q", "10-K", "8-K"]),
        ],
        primary_focus=["agency_rmbs"],
        has_monthly_update=True,
        has_financial_supplement=False,
        has_investor_presentation=False,
        notes="Pure Agency RMBS. Externally managed by Bimini Capital (BMNM). Monthly portfolio characteristics reports. Both pass-through and structured Agency RMBS (IOs, IIOs, POs). ~$5B portfolio.",
        check_cadence="weekly",
    ),
}


def get_company_config(ticker: str) -> CompanyConfig | None:
    """Look up a company config by ticker."""
    return COMPANY_REGISTRY.get(ticker.upper())


def get_all_tickers() -> list[str]:
    """Return all registered ticker symbols."""
    return list(COMPANY_REGISTRY.keys())
