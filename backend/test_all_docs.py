"""Run all metrics on test_docs and summarize results."""
import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app.store import create_entry, get_entry
from app.extractor import run_extraction

TEST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_docs")

def run_all():
    results = {}
    pdf_files = [f for f in os.listdir(TEST_DIR) if f.endswith(".pdf")]
    print(f"Found {len(pdf_files)} PDFs in test_docs/\n")

    for i, filename in enumerate(sorted(pdf_files), 1):
        filepath = os.path.join(TEST_DIR, filename)
        short_name = filename[:50]
        print(f"[{i}/{len(pdf_files)}] {short_name}...")

        with open(filepath, "rb") as f:
            pdf_bytes = f.read()

        import uuid
        paper_id = str(uuid.uuid4())
        create_entry(paper_id, pdf_bytes)

        start = time.time()
        try:
            run_extraction(paper_id)
        except Exception as e:
            print(f"  ERROR: {e}")
            results[filename] = {"error": str(e)}
            continue
        elapsed = time.time() - start

        entry = get_entry(paper_id)
        metadata = entry.get("metadata")
        image_eval = entry.get("image_evaluation", [])
        metadata_eval = entry.get("metadata_evaluation", {})
        cherry_eval = entry.get("cherry_picking_evaluation", {})
        lie_eval = entry.get("lie_factor_evaluation", {})
        graph_eval = entry.get("graph_evaluation", {})
        visual_assets = entry.get("visual_assets", [])

        results[filename] = {
            "time_s": round(elapsed, 1),
            "title": metadata.get("title") if metadata else None,
            "journal": metadata.get("journal") if metadata else None,
            "num_visual_assets": len(visual_assets),
            "num_charts": len([a for a in visual_assets if a.get("type") == "chart"]),
            "num_images": len([a for a in visual_assets if a.get("type") == "image"]),
            "ai_detection": {
                "total_evaluated": len(image_eval),
                "ai_generated": len([e for e in image_eval if e.get("ai_label") == "ai_generated"]),
                "natural": len([e for e in image_eval if e.get("ai_label") == "natural"]),
                "errors": len([e for e in image_eval if e.get("ai_label") == "error"]),
            },
            "credibility": {
                "predatory_check": metadata_eval.get("predatory_check"),
                "predatory_journal": metadata_eval.get("predatory_journal"),
                "mncs_score": metadata_eval.get("mncs_score"),
                "errors": metadata_eval.get("errors", []),
            },
            "cherry_picking": {
                "score": cherry_eval.get("score"),
                "severity": cherry_eval.get("severity"),
                "errors": cherry_eval.get("errors", []),
            },
            "lie_factor": {
                "worst_lie_factor": lie_eval.get("worst_lie_factor"),
                "all_passed": lie_eval.get("all_passed"),
                "errors": lie_eval.get("errors", []),
            },
            "graph_misleading": {
                "score": graph_eval.get("score"),
                "verdict": graph_eval.get("verdict"),
                "errors": graph_eval.get("errors", []),
            },
        }
        print(f"  Done in {elapsed:.1f}s")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    for fname, data in results.items():
        print(f"\n{'─' * 70}")
        print(f"  {fname[:60]}")
        if "error" in data and isinstance(data.get("error"), str):
            print(f"  ❌ FAILED: {data['error']}")
            continue
        print(f"  Title: {data.get('title', 'N/A')}")
        print(f"  Journal: {data.get('journal', 'N/A')}")
        print(f"  Time: {data['time_s']}s | Assets: {data['num_visual_assets']} ({data['num_charts']} charts, {data['num_images']} images)")
        print(f"  AI Detection: {data['ai_detection']}")
        print(f"  Credibility: {data['credibility']}")
        print(f"  Cherry Picking: {data['cherry_picking']}")
        print(f"  Lie Factor: {data['lie_factor']}")
        print(f"  Graph Misleading: {data['graph_misleading']}")

if __name__ == "__main__":
    run_all()
