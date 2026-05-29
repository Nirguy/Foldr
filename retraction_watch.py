"""
Retraction Watch Database Checker

Checks whether an author, paper title, or journal has entries in the
Retraction Watch Database (maintained by Crossref).

NEW: You can now just provide a paper title and it will automatically
look up the full metadata (authors, journal) from OpenAlex and check
everything at once.

Data source: https://gitlab.com/crossref/retraction-watch-data

Usage:
    # Quick check — just give a paper title:
    python retraction_watch.py "Signing at the beginning makes ethics salient"

    # Manual check with specific fields:
    python retraction_watch.py --author "Dan Ariely" --title "Signing" --journal "PNAS"
"""

import pandas as pd
import requests
import io
import os
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RETRACTION_WATCH_CSV_URL = (
    "https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv"
)

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
CACHE_FILE = os.path.join(CACHE_DIR, "retraction_watch.csv")
CACHE_MAX_AGE_HOURS = 24


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_db_cache: Optional[pd.DataFrame] = None  # in-memory cache for repeated calls


def _is_file_cache_valid() -> bool:
    """Check if the local CSV cache exists and is fresh enough."""
    if not os.path.exists(CACHE_FILE):
        return False
    modified_time = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
    age_hours = (datetime.now() - modified_time).total_seconds() / 3600
    return age_hours < CACHE_MAX_AGE_HOURS


def _load_database() -> pd.DataFrame:
    """
    Load the Retraction Watch database. Uses:
    1. In-memory cache (instant, same Python session)
    2. Local file cache (fast, refreshed every 24h)
    3. Download from GitLab (slow, only when needed)
    """
    global _db_cache

    if _db_cache is not None:
        return _db_cache

    if _is_file_cache_valid():
        _db_cache = pd.read_csv(CACHE_FILE, dtype=str)
        return _db_cache

    print("[retraction_watch] Downloading database from Crossref GitLab...")
    print("                   (first run only — cached locally after this)")

    response = requests.get(RETRACTION_WATCH_CSV_URL, timeout=180)
    response.raise_for_status()

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "wb") as f:
        f.write(response.content)

    _db_cache = pd.read_csv(io.BytesIO(response.content), dtype=str)
    print(f"[retraction_watch] Done. {len(_db_cache)} records loaded.")
    return _db_cache


# ---------------------------------------------------------------------------
# OpenAlex lookup — resolve paper metadata automatically
# ---------------------------------------------------------------------------

def _lookup_paper_metadata(title: str) -> dict:
    """
    Look up a paper on OpenAlex by title.
    Returns {title, authors, journal} with full proper names.
    """
    try:
        r = requests.get(
            f"https://api.openalex.org/works",
            params={"search": title, "per_page": 1,
                    "select": "id,display_name,authorships,primary_location"},
            timeout=30,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            return {}

        work = results[0]
        authors = [a["author"]["display_name"]
                   for a in work.get("authorships", [])
                   if a.get("author", {}).get("display_name")]

        journal = ""
        loc = work.get("primary_location", {})
        if loc and loc.get("source"):
            journal = loc["source"].get("display_name", "")

        return {
            "title": work.get("display_name", ""),
            "authors": authors,
            "journal": journal,
        }
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Public API — single function
# ---------------------------------------------------------------------------

def check_retraction_watch(
    author: Optional[str] = None,
    title: Optional[str] = None,
    journal: Optional[str] = None,
) -> dict:
    """
    Check the Retraction Watch Database for entries matching the given inputs.

    Parameters
    ----------
    author : str, optional
        Author name (partial, case-insensitive match).
    title : str, optional
        Paper title (partial, case-insensitive match). Special characters
        are normalized for flexible matching.
    journal : str, optional
        Journal name (partial, case-insensitive match).

    Returns
    -------
    dict
        A dictionary with the count of retraction records found for each input.
        Keys are "author", "title", "journal". Value is an integer (0 if not
        found or if that parameter was not provided).

        Example: {"author": 3, "title": 1, "journal": 45}
    """
    df = _load_database()

    result = {
        "author": 0,
        "title": 0,
        "journal": 0,
    }

    if author:
        mask = df["Author"].str.contains(author, case=False, na=False)
        result["author"] = int(mask.sum())

    if title:
        # Normalize: remove special dashes, quotes, extra spaces
        import re
        normalized_title = re.sub(r'[\u2013\u2014\u2012\u2015\u2018\u2019\u201c\u201d]', ' ', title)
        normalized_title = re.sub(r'[^\w\s]', ' ', normalized_title)
        # Use first few significant words for matching
        words = normalized_title.split()[:6]
        search_pattern = ".*".join(re.escape(w) for w in words if len(w) > 2)

        if search_pattern:
            mask = df["Title"].str.contains(search_pattern, case=False, na=False, regex=True)
            result["title"] = int(mask.sum())

    if journal:
        mask = df["Journal"].str.contains(journal, case=False, na=False)
        result["journal"] = int(mask.sum())

    return result


# ---------------------------------------------------------------------------
# CLI for quick manual testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Check the Retraction Watch Database."
    )
    parser.add_argument("paper", nargs="*", help="Paper title (auto-resolves authors & journal via OpenAlex)")
    parser.add_argument("--author", type=str, help="Author name to search")
    parser.add_argument("--title", type=str, help="Paper title to search")
    parser.add_argument("--journal", type=str, help="Journal name to search")

    args = parser.parse_args()

    # Mode 1: Just a paper title — auto-resolve everything
    if args.paper:
        paper_title = " ".join(args.paper)
        print(f"\n[lookup] Searching OpenAlex for: '{paper_title}'...")
        meta = _lookup_paper_metadata(paper_title)

        if not meta:
            print("[lookup] Paper not found on OpenAlex. Falling back to direct title search.\n")
            result = check_retraction_watch(title=paper_title)
            print("--- Retraction Watch Results ---")
            print(f"  title: {result['title']} record(s) found")
        else:
            print(f"  Found: {meta['title']}")
            print(f"  Journal: {meta['journal']}")
            print(f"  Authors: {', '.join(meta['authors'])}")
            print()

            # Check title — use normalized word matching (first 6 significant words)
            import re as _re
            # Remove "RETRACTED:" prefix that OpenAlex adds
            clean_title = _re.sub(r'^(RETRACTED|WITHDRAWN)\s*:\s*', '', meta["title"], flags=_re.IGNORECASE)
            normalized_title = _re.sub(r'[\u2013\u2014\u2012\u2015\u2018\u2019\u201c\u201d]', ' ', clean_title)
            normalized_title = _re.sub(r'[^\w\s]', ' ', normalized_title)
            words = normalized_title.split()[:6]
            search_pattern = ".*".join(_re.escape(w) for w in words if len(w) > 2)

            df = _load_database()
            if search_pattern:
                title_mask = df["Title"].str.contains(search_pattern, case=False, na=False, regex=True)
                title_count = int(title_mask.sum())
            else:
                title_count = 0
            result_title = {"title": title_count}

            # Check journal (full name from OpenAlex)
            result_journal = check_retraction_watch(journal=meta["journal"]) if meta["journal"] else {"journal": 0}

            # Check each author
            author_results = {}
            for author in meta["authors"]:
                # Use full name first
                r = check_retraction_watch(author=author)
                author_results[author] = r["author"]

            # Print results
            print()
            print(f"journal: {result_journal['journal']} retractions")
            print(f"title: {result_title['title']} retractions")
            for author, count in author_results.items():
                print(f"{author}: {count} retractions")

    # Mode 2: Manual flags
    elif any([args.author, args.title, args.journal]):
        result = check_retraction_watch(
            author=args.author,
            title=args.title,
            journal=args.journal,
        )

        print("\n--- Retraction Watch Results ---")
        for key, count in result.items():
            if count > 0:
                print(f"  {key}: {count} record(s) found")
            else:
                print(f"  {key}: clean (0 records)")
        print()

    else:
        parser.print_help()
        print("\n[TIP] Just provide a paper title:")
        print('  python retraction_watch.py "Signing at the beginning makes ethics salient"')
        exit(1)
