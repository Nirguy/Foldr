"""
Module to check if a publisher or journal appears on Beall's List of potentially
predatory publishers and standalone journals (https://beallslist.net/).
"""

import re
from functools import lru_cache

import requests
from bs4 import BeautifulSoup


BEALLS_PUBLISHERS_URL = "https://beallslist.net/"
BEALLS_JOURNALS_URL = "https://beallslist.net/standalone-journals/"


def _get_headers() -> dict:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }


def _parse_list_items(url: str) -> list[str]:
    """Fetch a Beall's List page and extract all <li> text entries."""
    response = requests.get(url, headers=_get_headers(), timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    entries = []
    for li in soup.find_all("li"):
        text = li.get_text(strip=True)
        if text:
            entries.append(text.lower())

    return entries


@lru_cache(maxsize=1)
def _fetch_publishers_list() -> list[str]:
    """Fetch the predatory publishers list. Cached in memory."""
    return _parse_list_items(BEALLS_PUBLISHERS_URL)


@lru_cache(maxsize=1)
def _fetch_journals_list() -> list[str]:
    """Fetch the standalone predatory journals list. Cached in memory."""
    return _parse_list_items(BEALLS_JOURNALS_URL)


def is_predatory(name: str) -> bool:
    """
    Check if a publisher or journal name appears on Beall's List.

    Args:
        name: The publisher or journal name to check.

    Returns:
        True if the name was found on Beall's List, False otherwise.
    """
    if not name or not name.strip():
        raise ValueError("Name cannot be empty.")

    query = name.strip().lower()

    publisher_entries = _fetch_publishers_list()
    if _find_matches(query, publisher_entries):
        return True

    journal_entries = _fetch_journals_list()
    if _find_matches(query, journal_entries):
        return True

    return False


def _find_matches(query: str, entries: list[str]) -> list[str]:
    """Find entries whose name or abbreviation exactly matches the query."""
    matched = []
    for entry in entries:
        # Extract the main name (before parentheses)
        entry_name = re.split(r'[\(\[]', entry)[0].strip().rstrip('.')

        # Extract abbreviations/aliases inside parentheses
        aliases = re.findall(r'\(([^)]+)\)', entry)
        aliases = [a.strip().lower() for a in aliases]

        # Match against the main name or any alias
        if query == entry_name or query.rstrip('.') == entry_name:
            matched.append(entry)
        elif query in aliases or query.rstrip('.') in aliases:
            matched.append(entry)
    return matched





# --- Example usage ---
if __name__ == "__main__":
    test_names = [
        "OMICS International",
        "Springer",
        "Frontiers",
        "Elsevier",
        "WASET",
        "Hikari Ltd",
        "Australasian Medical Journal",
    ]

    for name in test_names:
        result = is_predatory(name)
        status = "POTENTIALLY PREDATORY" if result else "Not found on list"
        print(f"{name}: {status}")
