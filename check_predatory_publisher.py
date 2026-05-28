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
    """Find entries that match the query using word-boundary and fuzzy matching."""
    matched = []
    for entry in entries:
        if _word_boundary_match(query, entry) or _fuzzy_match(query, entry):
            matched.append(entry)
    return matched


def _word_boundary_match(query: str, entry: str) -> bool:
    """
    Check if the query appears in the entry as a whole word/phrase,
    not as part of another word (e.g. "springer" should not match "mainspringer").
    """
    pattern = r'(?<![a-z])' + re.escape(query) + r'(?![a-z])'
    return bool(re.search(pattern, entry))


def _fuzzy_match(query: str, entry: str) -> bool:
    """
    Perform a slightly fuzzy match: check if all significant words
    in the query appear in the entry as whole words.
    """
    # Remove common short words that don't help matching
    stop_words = {"the", "of", "and", "for", "in", "a", "an", "to", "ltd", "inc"}
    query_words = [w for w in query.split() if w not in stop_words and len(w) > 2]

    if not query_words:
        return False

    # All significant words from the query must appear as whole words in the entry
    for word in query_words:
        pattern = r'(?<![a-z])' + re.escape(word) + r'(?![a-z])'
        if not re.search(pattern, entry):
            return False
    return True


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
