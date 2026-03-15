"""
Company registry — static configuration for known mREIT companies.
This supplements the companies table in Supabase with hardcoded 
configuration used during scraping and parsing.

Future companies are added here as templates, then inserted into
the Supabase companies table via the seed script.
"""

COMPANY_CONFIGS = {
    "ARR": {
        "name": "ARMOUR Residential REIT, Inc.",
        "cik": "0001428205",
        "exchange": "NYSE",
        "monthly_updates_url": "https://www.armourreit.com/news-events/monthly-company-updates",
        "quarterly_reports_url": "https://www.armourreit.com/financials/quarterly-reports",
        "annual_reports_url": "https://www.armourreit.com/financials/annual-reports",
        "news_url": "https://www.armourreit.com/news-events/news",
        "monthly_pdf_link_pattern": "/static-files/",
        "posting_schedule": {
            "monthly_update_day_range": [12, 23],  # Typically 12th-17th, 22nd-23rd in earnings months
            "earnings_months": [1, 2, 4, 7, 10],   # Months when quarterly earnings release
        },
    },
    # Future companies — uncomment and configure when ready
    # "AGNC": {
    #     "name": "AGNC Investment Corp.",
    #     "cik": "0001423689",
    #     "exchange": "NASDAQ",
    #     "monthly_updates_url": None,  # AGNC does monthly factor updates differently
    #     "quarterly_reports_url": "https://www.agnc.com/investors/financial-information/quarterly-results",
    #     "annual_reports_url": "https://www.agnc.com/investors/financial-information/annual-reports",
    #     "news_url": "https://www.agnc.com/investors/news-events/press-releases",
    # },
    # "NLY": {
    #     "name": "Annaly Capital Management, Inc.",
    #     "cik": "0001043219",
    #     "exchange": "NYSE",
    #     "quarterly_reports_url": "https://www.annaly.com/investors/financial-information/quarterly-results",
    # },
    # "TWO": {
    #     "name": "Two Harbors Investment Corp.",
    #     "cik": "0001576996",
    #     "exchange": "NYSE",
    # },
    # "DX": {
    #     "name": "Dynex Capital, Inc.",
    #     "cik": "0000826675",
    #     "exchange": "NYSE",
    # },
}

# Backfill URLs for ARMOUR monthly updates (March 2025 — March 2026)
ARMOUR_MONTHLY_BACKFILL = [
    ("2025-03", "2025-03-13", "https://www.armourreit.com/static-files/d0ebe47c-bc3c-4db7-9211-4765d82a3d71"),
    ("2025-04", "2025-04-23", "https://www.armourreit.com/static-files/2e359796-86ae-4c9a-9cce-47fc8ff2bcb2"),
    ("2025-05", "2025-05-16", "https://www.armourreit.com/static-files/a9e91427-7c9e-4886-8aaf-a8b4a13c4ae7"),
    ("2025-06", "2025-06-13", "https://www.armourreit.com/static-files/6352ff4f-4019-4cd8-9875-043b51bffc3a"),
    ("2025-07", "2025-07-23", "https://www.armourreit.com/static-files/5cd266ad-2264-4207-9370-d17b09d160c2"),
    ("2025-08", "2025-08-15", "https://www.armourreit.com/static-files/d090ab31-c67a-4dc2-880e-42904355425c"),
    ("2025-09", "2025-09-12", "https://www.armourreit.com/static-files/a6cc08fe-f154-4a7a-b7b1-699cfd08335e"),
    ("2025-10", "2025-10-22", "https://www.armourreit.com/static-files/50a84238-6dd3-4051-a3ee-3ea7a8276791"),
    ("2025-11", "2025-11-14", "https://www.armourreit.com/static-files/3288975d-7fbf-4b9a-99a0-695ade9f9c42"),
    ("2025-12", "2025-12-12", "https://www.armourreit.com/static-files/1942b9f3-78b4-44b8-bea5-b9f3251a49ac"),
    ("2026-01", "2026-01-16", "https://www.armourreit.com/static-files/6b3741b5-1cb3-4f01-8895-e8903e64b8d0"),
    ("2026-02", "2026-02-18", "https://www.armourreit.com/static-files/68039465-ebb5-49ba-8cc6-33e6f20ba32e"),
    ("2026-03", "2026-03-13", "https://www.armourreit.com/static-files/c40ff395-3917-41f6-8698-19c87315f4bc"),
]

# ARMOUR quarterly report URLs (2025 full year + Q4 2024 baseline)
ARMOUR_QUARTERLY_BACKFILL = [
    {
        "quarter": "Q4 2024",
        "period_end": "2024-12-31",
        "earnings_release_url": "https://www.armourreit.com/news-releases/news-release-details/armour-residential-reit-inc-announces-q4-results-and-december-0",
        "filing_10k_url": "https://www.armourreit.com/static-files/9a9fda44-9304-42ec-a5f3-e5434ac9a091",
    },
    {
        "quarter": "Q1 2025",
        "period_end": "2025-03-31",
        "earnings_release_url": "https://www.armourreit.com/news-releases/news-release-details/armour-residential-reit-inc-announces-q1-results-and-march-31-1",
        "filing_10q_url": "https://www.armourreit.com/static-files/3ccbaf0d-c629-4b90-836f-e24ee077bc12",
    },
    {
        "quarter": "Q2 2025",
        "period_end": "2025-06-30",
        "earnings_release_url": "https://www.armourreit.com/news-releases/news-release-details/armour-residential-reit-inc-announces-q2-results-and-june-30-2",
        "filing_10q_url": "https://www.armourreit.com/static-files/6aea66f0-8744-4a63-ba99-081140cc23c5",
    },
    {
        "quarter": "Q3 2025",
        "period_end": "2025-09-30",
        "earnings_release_url": "https://www.armourreit.com/news-releases/news-release-details/armour-residential-reit-inc-announces-q3-results-and-september-2",
        "filing_10q_url": "https://www.armourreit.com/static-files/365c8574-5ea5-45dc-8b13-71fa4ee7bbea",
    },
    {
        "quarter": "Q4 2025",
        "period_end": "2025-12-31",
        "earnings_release_url": "https://www.armourreit.com/news-releases/news-release-details/armour-residential-reit-inc-announces-q4-results-and-december-1",
        "filing_10k_url": "https://www.armourreit.com/static-files/0817cf11-99bc-41f4-9804-b9a9ab177f63",
        "investor_presentation_url": "https://www.armourreit.com/static-files/a3d43d3f-556e-49b3-8432-c285ddd92cb0",
    },
]
