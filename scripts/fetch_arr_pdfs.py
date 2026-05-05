"""
Fetch ARMOUR Residential (ARR) monthly update PDFs.
Try the company IR page first; fall back to SEC EDGAR 8-K filings.
"""
import asyncio
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SEC_HEADERS = {
    "User-Agent": "Tom Bot heath.maxwell@gmail.com",
    "Accept": "application/json",
}

ARR_IR_URL = "https://www.armourreit.com/news-events/monthly-company-updates"
ARR_CIK = "0001428205"
EDGAR_FILINGS_URL = (
    f"https://efts.sec.gov/LATEST/search-index?q=%22monthly+portfolio%22"
    f"&dateRange=custom&startdt=2026-01-01&enddt=2026-12-31"
    f"&entity=ARMOUR+Residential&forms=8-K"
)
EDGAR_JSON_URL = (
    f"https://data.sec.gov/submissions/CIK{ARR_CIK.lstrip('0').zfill(10)}.json"
)


async def try_company_ir(client: httpx.AsyncClient) -> list[dict]:
    """Try fetching direct from ARMOUR IR page."""
    print(f"\n--- Attempting ARMOUR IR page: {ARR_IR_URL}")
    try:
        resp = await client.get(ARR_IR_URL, headers=BROWSER_HEADERS, timeout=20.0)
        print(f"Status: {resp.status_code}")
        if resp.status_code != 200:
            print("Non-200 — skipping")
            return []
        html = resp.text
        print(f"HTML length: {len(html)} chars")
        print("First 500 chars:")
        print(html[:500])
        soup = BeautifulSoup(html, "lxml")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if href.lower().endswith(".pdf") and any(
                kw in text.lower() for kw in ["march", "april", "2026", "monthly"]
            ):
                full_url = urljoin(ARR_IR_URL, href)
                links.append({"url": full_url, "title": text})
                print(f"  Found PDF: {text} → {full_url}")
        return links
    except Exception as e:
        print(f"IR page fetch failed: {e}")
        return []


async def get_arr_8k_filings(client: httpx.AsyncClient) -> list[dict]:
    """
    Fetch recent ARR 8-K filings from EDGAR submissions JSON.
    Returns list of {accession, date, description} for 2026 filings.
    """
    cik_padded = ARR_CIK.lstrip("0").zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    print(f"\n--- Fetching EDGAR submissions: {url}")
    resp = await client.get(url, headers=SEC_HEADERS, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    descriptions = recent.get("primaryDocument", [])

    results = []
    for form, date, acc, desc in zip(forms, dates, accessions, descriptions):
        if form == "8-K" and date.startswith("2026"):
            results.append({
                "accession": acc,
                "date": date,
                "primary_doc": desc,
            })
            print(f"  8-K: {date} | {acc} | {desc}")

    return results


async def get_filing_documents(client: httpx.AsyncClient, accession: str) -> list[dict]:
    """Get all documents in an EDGAR filing."""
    acc_clean = accession.replace("-", "")
    cik = ARR_CIK.lstrip("0")
    index_url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_clean}/"
        f"{accession}-index.htm"
    )
    print(f"\n  Filing index: {index_url}")
    try:
        resp = await client.get(index_url, headers=SEC_HEADERS, timeout=15.0)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        docs = []
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 3:
                link = row.find("a", href=True)
                if link:
                    href = link["href"]
                    full_url = urljoin("https://www.sec.gov", href)
                    doc_type = cells[0].get_text(strip=True)
                    doc_desc = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    docs.append({"url": full_url, "type": doc_type, "desc": doc_desc})
                    print(f"    {doc_type:20s} {doc_desc:40s} {full_url}")
        return docs
    except Exception as e:
        print(f"  Filing index fetch failed: {e}")
        return []


async def main():
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # Try IR page first
        ir_pdfs = await try_company_ir(client)

        if ir_pdfs:
            print("\n=== Found PDFs on IR page ===")
            for p in ir_pdfs:
                print(f"  {p['title']} → {p['url']}")
            return ir_pdfs

        # Fall back to EDGAR
        print("\n=== Falling back to SEC EDGAR ===")
        filings = await get_arr_8k_filings(client)

        if not filings:
            print("No 2026 8-K filings found")
            return []

        # Get the two most recent (likely March and April 2026 monthly updates)
        recent_two = filings[:4]  # grab 4 to have options
        print(f"\nProcessing {len(recent_two)} most recent 2026 8-K filings:")

        all_docs = []
        for filing in recent_two:
            docs = await get_filing_documents(client, filing["accession"])
            for doc in docs:
                doc["filing_date"] = filing["date"]
                doc["accession"] = filing["accession"]
            all_docs.extend(docs)

        # Find PDFs or HTM documents that look like monthly updates
        monthly_docs = []
        for doc in all_docs:
            url_lower = doc["url"].lower()
            desc_lower = doc["desc"].lower()
            if any(kw in desc_lower or kw in url_lower for kw in
                   ["monthly", "portfolio", "update", "press"]):
                monthly_docs.append(doc)
            elif doc["url"].lower().endswith(".pdf"):
                monthly_docs.append(doc)

        if not monthly_docs:
            # Just grab primary documents from each filing
            monthly_docs = [d for d in all_docs if d["type"] in ("8-K", "EX-99.1", "EX-99")]

        print("\n=== Candidate documents for monthly updates ===")
        for d in monthly_docs:
            print(f"  [{d['filing_date']}] {d['type']:20s} {d['desc']:30s} {d['url']}")

        return monthly_docs


if __name__ == "__main__":
    results = asyncio.run(main())
    print(f"\n\nTotal candidate documents: {len(results)}")
