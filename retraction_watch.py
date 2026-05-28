"""
Retraction Watch Database Checker

A single-function module that checks whether an author, paper title, or journal
has entries in the Retraction Watch Database (maintained by Crossref).

Data source: https://gitlab.com/crossref/retraction-watch-data
The CSV is publicly available and updated daily. No API key required.

Usage:
    from retraction_watch import check_retraction_watch

    result = check_retraction_watch(
        author="John Smith",
        title="A Novel Method for Detecting Trace Metals",
        journal="Analytical Chemistry"
    )
    # result = {"author": 3, "title": 1, "journal": 45}
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
        Paper title (partial, case-insensitive match).
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
        mask = df["Title"].str.contains(title, case=False, na=False)
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
        description="Check the Retraction Watch Database for author/title/journal."
    )
    parser.add_argument("--author", type=str, help="Author name to search")
    parser.add_argument("--title", type=str, help="Paper title to search")
    parser.add_argument("--journal", type=str, help="Journal name to search")

    args = parser.parse_args()

    if not any([args.author, args.title, args.journal]):
        parser.print_help()
        print("\n[ERROR] Provide at least one of: --author, --title, --journal")
        exit(1)

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
