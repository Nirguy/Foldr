"""
Co-authorship Network POC — Paper-based query

Given a paper title, this script:
1. Finds the paper on OpenAlex
2. Gets all authors and their co-authors within the same subfield
3. Builds a co-authorship graph with Newman weights
4. Computes prominence scores (betweenness centrality)
5. Exports as GraphML for visualization in yEd

Usage:
    python authors_network.py "On Kim-Independence"
    python authors_network.py "Attention Is All You Need"
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import networkx as nx
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OPENALEX_API_BASE = "https://api.openalex.org"
MAILTO = None  # Set your email for better rate limits
API_KEY = None
MAX_WORKERS = 5
OUTPUT_DIR = "."


def _params(**kwargs):
    p = dict(kwargs)
    if API_KEY:
        p["api_key"] = API_KEY
    elif MAILTO:
        p["mailto"] = MAILTO
    return p


# ---------------------------------------------------------------------------
# OpenAlex queries
# ---------------------------------------------------------------------------

def find_paper(title: str) -> dict | None:
    """Find a paper by title on OpenAlex."""
    r = requests.get(f"{OPENALEX_API_BASE}/works", params=_params(
        search=title, per_page=1,
        select="id,display_name,authorships,primary_topic"
    ), timeout=30)
    r.raise_for_status()
    results = r.json().get("results", [])
    return results[0] if results else None


def get_author_papers(author_id: str, topic_id: str = None) -> list[dict]:
    """Get all papers by an author, optionally filtered by topic."""
    short_id = author_id.split("/")[-1]
    filt = f"author.id:{short_id}"
    if topic_id:
        filt += f",primary_topic.id:{topic_id}"

    papers = []
    page = 1
    while True:
        r = requests.get(f"{OPENALEX_API_BASE}/works", params=_params(
            filter=filt, per_page=100, page=page,
            select="id,display_name,authorships,cited_by_count"
        ), timeout=30)
        if r.status_code != 200:
            break
        results = r.json().get("results", [])
        if not results:
            break
        papers.extend(results)
        if len(results) < 100:
            break
        page += 1
        time.sleep(0.1)
    return papers


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_paper_graph(paper_title: str):
    """
    Build a co-authorship graph centered on a paper's authors.
    Exports GraphML for yEd.
    """
    print(f"[1/5] Searching for paper: '{paper_title}'...")
    paper = find_paper(paper_title)
    if not paper:
        print("Paper not found on OpenAlex.")
        return

    print(f"  Found: {paper['display_name']}")

    # Extract authors
    authors = {}
    for a in paper.get("authorships", []):
        info = a.get("author", {})
        aid = info.get("id")
        name = info.get("display_name", "Unknown")
        if aid:
            authors[aid] = name

    if not authors:
        print("No authors found.")
        return

    print(f"  Authors: {', '.join(authors.values())}")

    # Get topic for filtering
    topic = paper.get("primary_topic", {})
    topic_id = topic.get("id", "").split("/")[-1] if topic else None
    topic_name = topic.get("display_name", "Unknown") if topic else "Unknown"
    print(f"  Topic: {topic_name}")

    # Fetch co-author papers
    print(f"\n[2/5] Fetching papers for {len(authors)} authors (topic: {topic_name})...")
    all_papers = []
    all_authors = dict(authors)  # start with paper authors

    for aid, name in authors.items():
        print(f"  Fetching: {name}...")
        papers = get_author_papers(aid, topic_id)
        all_papers.extend(papers)
        for p in papers:
            for a in p.get("authorships", []):
                co_id = a.get("author", {}).get("id")
                co_name = a.get("author", {}).get("display_name", "Unknown")
                if co_id:
                    all_authors[co_id] = co_name

    print(f"  Found {len(all_papers)} papers, {len(all_authors)} authors in network.")

    # Fetch 1-hop co-author papers for inter-connections
    print(f"\n[3/5] Fetching co-author connections...")
    coauthor_ids = [aid for aid in all_authors if aid not in authors]

    def fetch_coauthor(cid):
        try:
            return get_author_papers(cid, topic_id)
        except Exception:
            return []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_coauthor, cid): cid for cid in coauthor_ids}
        done = 0
        for future in as_completed(futures):
            done += 1
            if done % 10 == 0:
                print(f"  {done}/{len(coauthor_ids)} co-authors processed...")
            all_papers.extend(future.result())

    # Build graph
    print(f"\n[4/5] Building graph...")
    G = nx.Graph()
    for aid, name in all_authors.items():
        G.add_node(aid, label=name)

    processed = set()
    for p in all_papers:
        pid = p.get("id")
        if pid in processed:
            continue
        processed.add(pid)

        paper_authors = [a["author"]["id"] for a in p.get("authorships", [])
                         if a.get("author", {}).get("id") in all_authors]
        n_p = len(paper_authors)
        if n_p < 2:
            continue
        w = 1.0 / (n_p - 1)
        for i in range(len(paper_authors)):
            for j in range(i + 1, len(paper_authors)):
                a1, a2 = paper_authors[i], paper_authors[j]
                if G.has_edge(a1, a2):
                    G[a1][a2]["weight"] += w
                else:
                    G.add_edge(a1, a2, weight=w)

    print(f"  Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # Compute prominence
    print(f"\n[5/5] Computing prominence scores...")
    if G.number_of_nodes() < 3:
        print("  Graph too small.")
        return

    betweenness = nx.betweenness_centrality(G, weight="weight", normalized=False)
    scores = list(betweenness.values())
    min_s, max_s = min(scores), max(scores)

    for aid in G.nodes():
        raw = betweenness[aid]
        norm = (raw - min_s) / (max_s - min_s) if max_s > min_s else 0.5
        G.nodes[aid]["prominence"] = round(norm, 4)
        G.nodes[aid]["is_paper_author"] = aid in authors

    # Mark paper authors
    for aid in authors:
        if aid in G.nodes:
            G.nodes[aid]["is_paper_author"] = True

    # Export GraphML (yEd compatible)
    safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in paper_title)[:40]
    graphml_file = f"{OUTPUT_DIR}/{safe_title}.graphml"
    nx.write_graphml(G, graphml_file)
    print(f"\n  Exported GraphML: {graphml_file}")

    # Export as image (PNG)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        plt.figure(figsize=(16, 12))
        pos = nx.spring_layout(G, k=2, iterations=50, seed=42)

        # Node sizes based on prominence
        sizes = [300 + G.nodes[n].get("prominence", 0) * 3000 for n in G.nodes()]
        colors = ["#ff4444" if G.nodes[n].get("is_paper_author") else "#4488cc"
                  for n in G.nodes()]

        # Draw
        nx.draw_networkx_edges(G, pos, alpha=0.2, width=0.5)
        nx.draw_networkx_nodes(G, pos, node_size=sizes, node_color=colors, alpha=0.8)

        # Labels only for paper authors and high-prominence nodes
        labels = {}
        for n in G.nodes():
            if G.nodes[n].get("is_paper_author") or G.nodes[n].get("prominence", 0) > 0.3:
                labels[n] = G.nodes[n].get("label", "")
        nx.draw_networkx_labels(G, pos, labels, font_size=8)

        plt.title(f"Co-authorship Network: {paper['display_name']}\n"
                  f"Red = paper authors | Size = prominence", fontsize=11)
        plt.axis("off")
        plt.tight_layout()

        img_file = f"{OUTPUT_DIR}/{safe_title}.png"
        plt.savefig(img_file, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Exported image: {img_file}")
    except ImportError:
        print("  (Install matplotlib for image export: pip install matplotlib)")

    # Print results
    print(f"\n{'='*60}")
    print(f"  Paper: {paper['display_name']}")
    print(f"  Topic: {topic_name}")
    print(f"  Network: {G.number_of_nodes()} authors, {G.number_of_edges()} connections")
    print(f"\n  Author Prominence Scores:")
    for aid, name in authors.items():
        if aid in G.nodes:
            score = G.nodes[aid]["prominence"]
            print(f"    {name}: {score:.4f}")
    print(f"{'='*60}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
    else:
        title = " ".join(sys.argv[1:])
        build_paper_graph(title)
