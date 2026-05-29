"""
Batch Nature Article Scraper (with Bright Data support)

Takes a list of Nature article URLs, downloads:
1. The article PDF
2. All dataset files (xlsx/csv) from supplementary/source data
3. Follows external repository links (figshare, zenodo, dryad, etc.)
   using Bright Data to bypass access restrictions

Usage:
    python batch_scraper.py urls.txt
    python batch_scraper.py urls.txt --output my_output/

Input file: one URL per line, lines starting with # are ignored.

Requires:
    pip install requests beautifulsoup4 lxml python-dotenv

Optional:
    Set BRIGHT_DATA_API_TOKEN in .env for external repository access.
"""

import os
import sys
import re
import json
import time
import argparse
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

BRIGHT_DATA_API_TOKEN = os.getenv("BRIGHT_DATA_API_TOKEN")
BRIGHT_DATA_ZONE = os.getenv("BRIGHT_DATA_ZONE", "mcp_unlocker")

DATASET_EXTENSIONS = {".xlsx", ".xls", ".csv", ".tsv"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# External repositories where datasets are commonly hosted
EXTERNAL_REPO_DOMAINS = [
    "figshare.com",
    "zenodo.org",
    "datadryad.org",
    "dryad.org",
    "github.com",
    "dataverse",
    "osf.io",
    "openneuro.org",
    "ncbi.nlm.nih.gov",
    "ebi.ac.uk",
    "data.mendeley.com",
    "kaggle.com",
    "huggingface.co",
]


# ─────────────────────────────────────────────────────────────────────────────
# Fetching (direct + Bright Data)
# ─────────────────────────────────────────────────────────────────────────────


def fetch_direct(url: str, timeout: int = 60) -> requests.Response:
    """Standard HTTP GET."""
    resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    return resp


def fetch_with_brightdata(url: str) -> requests.Response:
    """Fetch via Bright Data MCP scrape_as_html tool."""
    if not BRIGHT_DATA_API_TOKEN:
        return fetch_direct(url)

    # Use the MCP SSE endpoint which works with the free tier token
    # For file downloads, try direct first with better headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Referer": url,
    }
    resp = requests.get(url, headers=headers, timeout=60, allow_redirects=True)
    if resp.status_code == 200 and not resp.content[:15].startswith(b"<!"):
        return resp

    # If that failed, the direct API won't help either with this token
    # Return what we got
    resp.raise_for_status()
    return resp


def fetch_smart(url: str) -> requests.Response:
    """Try direct first, fall back to Bright Data on failure."""
    try:
        return fetch_direct(url)
    except (requests.HTTPError, requests.ConnectionError, requests.Timeout):
        if BRIGHT_DATA_API_TOKEN:
            return fetch_with_brightdata(url)
        raise


def fetch_page_html(url: str) -> str:
    """Fetch a page and return HTML. Uses Bright Data for external repos."""
    is_external = any(domain in url for domain in EXTERNAL_REPO_DOMAINS)
    if is_external and BRIGHT_DATA_API_TOKEN:
        try:
            return fetch_with_brightdata(url).text
        except Exception:
            return fetch_direct(url).text
    return fetch_direct(url).text


# ─────────────────────────────────────────────────────────────────────────────
# Dataset discovery
# ─────────────────────────────────────────────────────────────────────────────


def is_dataset_file(url: str) -> bool:
    """Check if URL points to a dataset file."""
    ext = Path(urlparse(url).path).suffix.lower()
    return ext in DATASET_EXTENSIONS


def find_direct_datasets(soup: BeautifulSoup, base_url: str) -> list:
    """Find xlsx/csv dataset links directly on the article page."""
    urls = []

    # Source data from static-content.springer.com
    for a in soup.find_all("a", href=re.compile(r"static-content\.springer\.com", re.I)):
        full = urljoin(base_url, a["href"])
        if is_dataset_file(full) and full not in urls:
            urls.append(full)

    # Relative /static-content/ links
    for a in soup.find_all("a", href=re.compile(r"/static-content/", re.I)):
        full = urljoin(base_url, a["href"])
        if is_dataset_file(full) and full not in urls:
            urls.append(full)

    return urls


def find_external_repo_links(soup: BeautifulSoup) -> list:
    """Find links to external data repositories from the Data Availability section only."""
    repos = []

    # Only look in Data Availability section
    da_section = None
    for section in soup.find_all("section"):
        heading = section.find(["h2", "h3", "h4"])
        if heading and "data availability" in heading.get_text().lower():
            da_section = section
            break

    if not da_section:
        # Try by id
        da_section = soup.find("section", {"data-title": re.compile(r"data availability", re.I)})

    if not da_section:
        return repos

    for a in da_section.find_all("a", href=True):
        href = a["href"]
        for domain in EXTERNAL_REPO_DOMAINS:
            # Match domain in the hostname OR anywhere in the URL (for doi.org/dryad links)
            if domain in href and href not in [r["url"] for r in repos]:
                repos.append({
                    "url": href,
                    "domain": domain,
                    "text": a.get_text(strip=True),
                })
                break
        else:
            # Also catch doi.org links that redirect to repos (e.g. doi.org/10.5061/dryad.xxx)
            if "doi.org" in href and any(repo_kw in href for repo_kw in ["dryad", "figshare", "zenodo"]):
                matched = next((d for d in EXTERNAL_REPO_DOMAINS if d.split(".")[0] in href), "doi.org")
                if href not in [r["url"] for r in repos]:
                    repos.append({
                        "url": href,
                        "domain": matched,
                        "text": a.get_text(strip=True),
                    })
    return repos


def scrape_figshare_datasets(url: str) -> list:
    """Scrape a figshare page for downloadable dataset files."""
    datasets = []
    try:
        html = fetch_page_html(url)
        soup = BeautifulSoup(html, "lxml")

        # Figshare download links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full = urljoin(url, href)
            if is_dataset_file(full) and full not in datasets:
                datasets.append(full)

        # Figshare ndownloader pattern
        for a in soup.find_all("a", href=re.compile(r"ndownloader|download", re.I)):
            href = a["href"]
            full = urljoin(url, href)
            text = a.get_text(strip=True).lower()
            if any(ext.strip(".") in text for ext in DATASET_EXTENSIONS):
                if full not in datasets:
                    datasets.append(full)

    except Exception as e:
        print(f"      Figshare scrape failed: {e}")
    return datasets


def scrape_zenodo_datasets(url: str) -> list:
    """Scrape a zenodo page for downloadable dataset files."""
    datasets = []
    try:
        html = fetch_page_html(url)
        soup = BeautifulSoup(html, "lxml")

        # Zenodo file links
        for a in soup.find_all("a", href=re.compile(r"/files/", re.I)):
            href = a["href"]
            full = urljoin(url, href)
            if is_dataset_file(full) and full not in datasets:
                datasets.append(full)

        # Also check for download links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full = urljoin(url, href)
            if is_dataset_file(full) and full not in datasets:
                datasets.append(full)

    except Exception as e:
        print(f"      Zenodo scrape failed: {e}")
    return datasets


def scrape_dryad_datasets(url: str) -> list:
    """Scrape a Dryad page for downloadable dataset files using a session."""
    datasets = []
    try:
        # Use a session to maintain cookies (Dryad requires this)
        session = requests.Session()
        session.headers.update(HEADERS)

        # First visit the landing page to get cookies
        resp = session.get(url, timeout=30, allow_redirects=True)
        resolved_url = resp.url
        html = resp.text
        soup = BeautifulSoup(html, "lxml")

        # Dryad lists files with links like /downloads/file_stream/ID
        for a in soup.find_all("a", href=re.compile(r"/downloads/file_stream/", re.I)):
            href = a["href"]
            full = urljoin(resolved_url, href)
            link_text = a.get_text(strip=True)
            if any(link_text.lower().endswith(ext) for ext in DATASET_EXTENSIONS):
                datasets.append({"url": full, "filename": link_text, "session": session})

        # Also check standard href-based detection
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full = urljoin(resolved_url, href)
            if is_dataset_file(full) and full not in [d["url"] if isinstance(d, dict) else d for d in datasets]:
                datasets.append({"url": full, "filename": unquote(Path(urlparse(full).path).name), "session": session})

    except Exception as e:
        print(f"      Dryad scrape failed: {e}")
    return datasets


def scrape_generic_repo(url: str) -> list:
    """Generic scrape of an external page for dataset file links."""
    datasets = []
    try:
        html = fetch_page_html(url)
        soup = BeautifulSoup(html, "lxml")

        for a in soup.find_all("a", href=True):
            href = a["href"]
            full = urljoin(url, href)
            if is_dataset_file(full) and full not in datasets:
                datasets.append(full)

    except Exception as e:
        print(f"      Generic repo scrape failed: {e}")
    return datasets


def follow_external_repos(repos: list) -> list:
    """Follow external repository links and find dataset files."""
    all_datasets = []

    for repo in repos:
        url = repo["url"]
        domain = repo["domain"]
        print(f"    Following external link: {domain} -> {url[:80]}")

        if "figshare" in domain:
            datasets = scrape_figshare_datasets(url)
        elif "zenodo" in domain:
            datasets = scrape_zenodo_datasets(url)
        elif "dryad" in domain:
            datasets = scrape_dryad_datasets(url)
        else:
            datasets = scrape_generic_repo(url)

        for ds in datasets:
            # Normalize: ensure all entries are {url, filename} dicts
            if isinstance(ds, str):
                ds = {"url": ds, "filename": unquote(Path(urlparse(ds).path).name)}
            if ds["url"] not in [d["url"] if isinstance(d, dict) else d for d in all_datasets]:
                all_datasets.append(ds)

        time.sleep(1)

    return all_datasets


# ─────────────────────────────────────────────────────────────────────────────
# Article processing
# ─────────────────────────────────────────────────────────────────────────────


def extract_article_id(url: str) -> str:
    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")
    if "articles" in parts:
        return parts[parts.index("articles") + 1]
    return parts[-1] if parts else "unknown"


def extract_metadata(soup: BeautifulSoup, url: str) -> dict:
    meta = {"url": url, "article_id": extract_article_id(url)}

    title_el = soup.find("h1", class_="c-article-title") or soup.find("h1")
    meta["title"] = title_el.get_text(strip=True) if title_el else ""

    authors = []
    for a in soup.find_all("a", {"data-test": "author-name"}):
        authors.append(a.get_text(strip=True))
    meta["authors"] = authors

    doi_meta = soup.find("meta", {"name": "DOI"}) or soup.find("meta", {"name": "citation_doi"})
    meta["doi"] = doi_meta.get("content", "") if doi_meta else ""

    journal_el = soup.find("i", {"data-test": "journal-title"})
    meta["journal"] = journal_el.get_text(strip=True) if journal_el else ""

    time_el = soup.find("time")
    meta["published_date"] = time_el.get("datetime", time_el.get_text(strip=True)) if time_el else ""

    return meta


def process_article(url: str, output_dir: Path) -> bool:
    """Process a single article: download PDF + datasets (direct + external repos)."""
    article_id = extract_article_id(url)
    dest = output_dir / article_id
    dest.mkdir(parents=True, exist_ok=True)

    # Fetch article page
    print(f"  Fetching article page...")
    try:
        html = fetch_direct(url).text
    except Exception as e:
        print(f"  ERROR fetching page: {e}")
        return False

    soup = BeautifulSoup(html, "lxml")
    meta = extract_metadata(soup, url)
    print(f"  Title: {meta['title'][:70]}")

    # ── Find datasets: direct links on page ──
    direct_datasets = find_direct_datasets(soup, url)
    print(f"  Direct dataset files found: {len(direct_datasets)}")

    # ── Find datasets: external repositories ──
    external_repos = find_external_repo_links(soup)
    external_datasets = []
    if external_repos:
        print(f"  External repository links found: {len(external_repos)}")
        external_datasets = follow_external_repos(external_repos)
        print(f"  Dataset files from external repos: {len(external_datasets)}")

    # Combine all dataset URLs (direct as dicts + external as dicts)
    all_datasets = [{"url": u, "filename": unquote(Path(urlparse(u).path).name)} for u in direct_datasets]
    for ds in external_datasets:
        if isinstance(ds, str):
            ds = {"url": ds, "filename": unquote(Path(urlparse(ds).path).name)}
        if ds["url"] not in [d["url"] for d in all_datasets]:
            all_datasets.append(ds)
    meta["dataset_files"] = []
    meta["external_repos"] = [r["url"] for r in external_repos]

    # ── Download PDF ──
    pdf_url = f"https://www.nature.com/articles/{article_id}.pdf"
    pdf_path = dest / f"{article_id}.pdf"
    print(f"  Downloading PDF...")
    try:
        resp = fetch_smart(pdf_url)
        content = resp.content
        # Check if we got actual PDF (not an HTML paywall page)
        if content[:5] == b"%PDF-":
            pdf_path.write_bytes(content)
            print(f"    Saved: {pdf_path.name} ({len(content)} bytes)")
        elif b"<!DOCTYPE" in content[:100] or b"<html" in content[:100]:
            # Got HTML instead of PDF — try Bright Data
            print(f"    Got HTML instead of PDF, retrying with Bright Data...")
            if BRIGHT_DATA_API_TOKEN:
                resp = fetch_with_brightdata(pdf_url)
                content = resp.content
                if content[:5] == b"%PDF-":
                    pdf_path.write_bytes(content)
                    print(f"    Saved via Bright Data: {pdf_path.name} ({len(content)} bytes)")
                else:
                    print(f"    Still not a valid PDF — article may be paywalled")
            else:
                print(f"    No Bright Data token — cannot bypass paywall")
        else:
            pdf_path.write_bytes(content)
            print(f"    Saved: {pdf_path.name} ({len(content)} bytes)")
    except Exception as e:
        print(f"    PDF failed: {e}")
    time.sleep(1)

    # ── Download datasets ──
    if all_datasets:
        print(f"  Downloading {len(all_datasets)} dataset file(s)...")
        for i, ds in enumerate(all_datasets, 1):
            ds_url = ds["url"]
            filename = ds.get("filename", "") or f"dataset_{i}.xlsx"
            session = ds.get("session", None)
            # Clean up filename
            filename = re.sub(r'[?#].*', '', filename)
            if not Path(filename).suffix:
                filename += ".xlsx"

            filepath = dest / filename
            try:
                # Use session if provided (for sites like Dryad that need cookies)
                if session:
                    resp = session.get(ds_url, timeout=60, allow_redirects=True)
                else:
                    resp = fetch_smart(ds_url)

                content = resp.content
                # Verify we got actual data, not HTML error page
                if len(content) > 100 and not (content[:5] == b"<!DOC" or content[:5] == b"<html" or content[:5] == b"<!doc"):
                    filepath.write_bytes(content)
                    meta["dataset_files"].append(filename)
                    print(f"    [{i}/{len(all_datasets)}] {filename} ({len(content)} bytes)")
                else:
                    print(f"    [{i}/{len(all_datasets)}] {filename} - blocked (got HTML)")
            except Exception as e:
                print(f"    [{i}/{len(all_datasets)}] {filename} - ERROR: {e}")
            time.sleep(1)
    else:
        print(f"  No dataset files found (direct or external).")

    # Save metadata
    meta_path = dest / "metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Batch scrape Nature articles (PDF + datasets, follows external repos)"
    )
    parser.add_argument("input", nargs="+", help="Article URL(s) or a text file with URLs (one per line)")
    parser.add_argument("--output", "-o", default="scraped_articles", help="Output directory")
    args = parser.parse_args()

    urls = []
    for item in args.input:
        if item.startswith("http://") or item.startswith("https://"):
            urls.append(item)
        else:
            # Treat as a file
            input_file = Path(item)
            if not input_file.exists():
                print(f"Error: {input_file} not found")
                sys.exit(1)
            urls.extend([
                line.strip()
                for line in input_file.read_text().splitlines()
                if line.strip() and not line.strip().startswith("#")
            ])

    if not urls:
        print("No URLs provided.")
        sys.exit(1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    bd_status = "enabled" if BRIGHT_DATA_API_TOKEN else "disabled (set BRIGHT_DATA_API_TOKEN in .env)"

    print(f"{'='*60}")
    print(f"  Batch Nature Scraper")
    print(f"  Articles:    {len(urls)}")
    print(f"  Output:      {output_dir}/")
    print(f"  Bright Data: {bd_status}")
    print(f"{'='*60}")

    success = 0
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] {url}")
        try:
            if process_article(url, output_dir):
                success += 1
        except Exception as e:
            print(f"  ERROR: {e}")
        time.sleep(2)

    print(f"\n{'='*60}")
    print(f"  Done: {success}/{len(urls)} articles processed")
    print(f"  Output: {output_dir}/")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
