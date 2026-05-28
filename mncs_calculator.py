"""
Module to calculate the Mean Normalized Citation Score (MNCS) for a
specific article using data from the OpenAlex API.

MNCS = article_citations / average_citations_in_same_field_and_year

- MNCS > 1.0 means the article is cited more than the field average.
- MNCS = 1.0 means it's exactly at the field average.
- MNCS < 1.0 means it's cited less than the field average.
"""

import requests

OPENALEX_API_BASE = "https://api.openalex.org"

# Optional: set your email for the polite pool (better rate limits, no key needed)
# Or set an API key if you have one.
MAILTO = None  # e.g. "your@email.com"
API_KEY = None  # e.g. "your_api_key"


def _build_params(**kwargs) -> dict:
    """Build query params, adding auth if configured."""
    params = dict(kwargs)
    if API_KEY:
        params["api_key"] = API_KEY
    elif MAILTO:
        params["mailto"] = MAILTO
    return params


def _search_work(title: str) -> dict | None:
    """
    Search OpenAlex for a work by title. Returns the best matching work
    object or None if not found.
    """
    params = _build_params(
        search=title,
        per_page=1,
        select="id,display_name,cited_by_count,publication_year,primary_topic",
    )

    response = requests.get(
        f"{OPENALEX_API_BASE}/works", params=params, timeout=30
    )
    response.raise_for_status()

    data = response.json()
    results = data.get("results", [])

    if not results:
        return None

    return results[0]


def _get_field_average_citations(topic_id: str, publication_year: int) -> float | None:
    """
    Calculate the average citation count for works in the same topic and
    publication year by sampling from OpenAlex.
    """
    # Strip the URL prefix if present to get just the ID for filtering
    # topic_id comes as "https://openalex.org/T12345" — we need "T12345"
    if "/" in topic_id:
        topic_short = topic_id.split("/")[-1]
    else:
        topic_short = topic_id

    # Get a sample of works in the same topic + year and compute average citations
    # We use a large sample for a reasonable estimate
    params = _build_params(
        filter=f"primary_topic.id:{topic_short},publication_year:{publication_year}",
        per_page=200,
        select="cited_by_count",
    )

    response = requests.get(
        f"{OPENALEX_API_BASE}/works", params=params, timeout=30
    )
    response.raise_for_status()

    data = response.json()
    results = data.get("results", [])

    if not results:
        return None

    total_citations = sum(work.get("cited_by_count", 0) for work in results)
    return total_citations / len(results)


def get_mncs(article_title: str) -> float | None:
    """
    Calculate the Mean Normalized Citation Score for an article.

    Args:
        article_title: The title of the article to look up.

    Returns:
        The MNCS value (float), or None if the article couldn't be found
        or the calculation couldn't be performed.
    """
    if not article_title or not article_title.strip():
        raise ValueError("Article title cannot be empty.")

    # Step 1: Find the article
    work = _search_work(article_title.strip())
    if not work:
        return None

    # Step 2: Extract needed fields
    cited_by_count = work.get("cited_by_count", 0)
    publication_year = work.get("publication_year")
    primary_topic = work.get("primary_topic")

    if not publication_year or not primary_topic:
        return None

    topic_id = primary_topic.get("id")
    if not topic_id:
        return None

    # Step 3: Get the field average
    field_avg = _get_field_average_citations(topic_id, publication_year)
    if not field_avg or field_avg == 0:
        return None

    # Step 4: Calculate MNCS
    return cited_by_count / field_avg


# --- Example usage ---
if __name__ == "__main__":
    test_articles = [
        "Attention Is All You Need",
        "Deep Residual Learning for Image Recognition",
        "BERT: Pre-training of Deep Bidirectional Transformers",
    ]

    for title in test_articles:
        score = get_mncs(title)
        if score is not None:
            print(f"{title}")
            print(f"   MNCS: {score:.2f}")
        else:
            print(f"{title}: Could not calculate MNCS")
        print()
