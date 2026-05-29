# Evaluator - connects parsed PDF data to evaluation modules
# Calls ai_image_detection, check_predatory_publisher, and mncs_calculator

import base64
import io
import sys
import os
import tempfile

# Add project root to path so we can import the evaluation modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai_image_detection import detect_ai_generated_image
from check_predatory_publisher import is_predatory
from mncs_calculator import get_mncs

# Also add lie_factor to path
from lie_factor import analyze_single as lie_factor_analyze_single


def evaluate_images(visual_assets: list[dict]) -> list[dict]:
    """Run AI image detection on each visual asset.

    Args:
        visual_assets: List of dicts with image_data (base64 PNG), page_number, type, etc.

    Returns:
        List of dicts with: page_number, type, ai_score, ai_label, ai_reasons.
    """
    results = []

    for asset in visual_assets:
        image_data = asset.get("image_data", "")
        if not image_data:
            continue

        # Decode base64 to bytes and write to a temp file (detect_ai_generated_image needs a path)
        try:
            img_bytes = base64.b64decode(image_data)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(img_bytes)
                temp_path = f.name

            try:
                result_str = detect_ai_generated_image(temp_path)
            finally:
                os.unlink(temp_path)

            # Parse the result string: "Likely AI-generated (score: 0.85; reasons: ...)"
            ai_label = "unknown"
            ai_score = 0.0
            ai_reasons = []

            if "Likely AI-generated" in result_str:
                ai_label = "ai_generated"
            elif "Likely natural" in result_str:
                ai_label = "natural"

            # Extract score
            if "score:" in result_str:
                try:
                    score_part = result_str.split("score:")[1].split(";")[0].strip().rstrip(")")
                    ai_score = float(score_part)
                except (ValueError, IndexError):
                    pass

            # Extract reasons
            if "reasons:" in result_str:
                try:
                    reasons_part = result_str.split("reasons:")[1].strip().rstrip(")")
                    if reasons_part and reasons_part != "none":
                        ai_reasons = [r.strip() for r in reasons_part.split(",")]
                except (IndexError):
                    pass

            results.append({
                "page_number": asset.get("page_number"),
                "type": asset.get("type", "unknown"),
                "ai_score": ai_score,
                "ai_label": ai_label,
                "ai_reasons": ai_reasons,
            })

        except Exception as e:
            results.append({
                "page_number": asset.get("page_number"),
                "type": asset.get("type", "unknown"),
                "ai_score": 0.0,
                "ai_label": "error",
                "ai_reasons": [str(e)[:100]],
            })

    return results


def evaluate_metadata(metadata: dict | None) -> dict:
    """Run predatory publisher check and MNCS calculation on metadata.

    Args:
        metadata: Dict with title, authors, institutions, journal, date.

    Returns:
        Dict with: predatory_check (bool|None), mncs_score (float|None), errors.
    """
    result = {
        "predatory_check": None,  # True = on Beall's list, False = not found, None = couldn't check
        "predatory_journal": None,
        "mncs_score": None,
        "mncs_title": None,
        "errors": [],
    }

    if not metadata:
        result["errors"].append("No metadata available")
        return result

    # Check predatory publisher/journal
    journal = metadata.get("journal")
    if journal:
        try:
            result["predatory_check"] = is_predatory(journal)
            result["predatory_journal"] = journal
        except Exception as e:
            result["errors"].append(f"Predatory check failed: {str(e)[:100]}")
    else:
        result["errors"].append("No journal name in metadata")

    # Calculate MNCS
    title = metadata.get("title")
    if title:
        try:
            mncs = get_mncs(title)
            result["mncs_score"] = mncs
            result["mncs_title"] = title
        except Exception as e:
            result["errors"].append(f"MNCS calculation failed: {str(e)[:100]}")
    else:
        result["errors"].append("No title in metadata")

    return result


def evaluate_lie_factor(visual_assets: list[dict], datasets: list[dict]) -> dict:
    """Run lie factor analysis on chart images vs dataset.

    Compares the visual representation of data in charts against the actual
    dataset values to detect exaggeration or minimization.

    Returns:
        Dict with: score (lie factor value), passed (bool), results (per-chart), errors.
    """
    import pandas as pd

    result = {
        "worst_lie_factor": None,
        "all_passed": True,
        "results": [],
        "errors": [],
    }

    chart_assets = [a for a in visual_assets if a.get("type") == "chart"]
    if not chart_assets:
        result["errors"].append("No chart images found in PDF")
        return result

    if not datasets:
        result["errors"].append("No dataset provided for lie factor analysis")
        return result

    # Get the first dataset with data
    dataset_entry = None
    for ds in datasets:
        if ds.get("columns") and ds.get("rows"):
            dataset_entry = ds
            break

    if not dataset_entry:
        result["errors"].append("Dataset has no parseable data")
        return result

    try:
        df = pd.DataFrame(dataset_entry["rows"], columns=dataset_entry["columns"])
        # Find first numeric column
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        if not numeric_cols:
            # Try converting
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

        if not numeric_cols:
            result["errors"].append("No numeric columns found in dataset")
            return result

        value_col = numeric_cols[0]
        worst_lf = None

        for chart in chart_assets[:3]:  # Limit to 3 charts
            image_data = chart.get("image_data", "")
            if not image_data:
                continue

            img_bytes = base64.b64decode(image_data)
            img_tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            img_tmp.write(img_bytes)
            img_tmp.close()

            try:
                lf_result = lie_factor_analyze_single(df, value_col, img_tmp.name)
                result["results"].append({
                    "page_number": chart.get("page_number"),
                    "lie_factor": lf_result.get("lie_factor"),
                    "passed": lf_result.get("passed", False),
                    "chart_type": lf_result.get("chart_type"),
                    "error": lf_result.get("error"),
                })
                if not lf_result.get("passed", False):
                    result["all_passed"] = False
                lf_val = lf_result.get("lie_factor")
                if lf_val is not None:
                    if worst_lf is None or abs(lf_val - 1.0) > abs(worst_lf - 1.0):
                        worst_lf = lf_val
            except Exception as e:
                result["errors"].append(f"Lie factor failed: {str(e)[:100]}")
            finally:
                os.unlink(img_tmp.name)

        result["worst_lie_factor"] = worst_lf

    except Exception as e:
        result["errors"].append(f"Lie factor setup failed: {str(e)[:150]}")

    return result


def evaluate_cherry_picking(visual_assets: list[dict], datasets: list[dict]) -> dict:
    """Run cherry picking detection on chart images + dataset.

    Requires at least one chart image and one dataset to compare against.

    Returns:
        Dict with: score (0-100, higher = more cherry-picked), severity, findings, errors.
    """
    result = {
        "score": 0,
        "severity": "None/Minimal",
        "cherry_findings": [],
        "legitimate_aspects": [],
        "mitigating_factors": [],
        "errors": [],
    }

    # Need both a chart image and a dataset
    chart_assets = [a for a in visual_assets if a.get("type") == "chart"]
    if not chart_assets:
        result["errors"].append("No chart images found in PDF")
        return result

    if not datasets:
        result["errors"].append("No dataset provided for comparison")
        return result

    # Get the first dataset that has actual data
    dataset_entry = None
    for ds in datasets:
        if ds.get("columns") and ds.get("rows"):
            dataset_entry = ds
            break

    if not dataset_entry:
        result["errors"].append("Dataset has no parseable data")
        return result

    try:
        # Write dataset to temp CSV
        import pandas as pd

        df = pd.DataFrame(dataset_entry["rows"], columns=dataset_entry["columns"])
        dataset_tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", newline="")
        df.to_csv(dataset_tmp.name, index=False)
        dataset_tmp.close()

        # Add cherry_picking to path
        cherry_picking_dir = os.path.join(PROJECT_ROOT, "cherry_picking")
        if cherry_picking_dir not in sys.path:
            sys.path.insert(0, cherry_picking_dir)

        from cherry_pick_detector import detect_cherry_picking

        # Run on each chart, take the worst score
        worst_score = 0
        all_findings = []

        for chart in chart_assets[:3]:  # Limit to 3 charts to avoid timeout
            image_data = chart.get("image_data", "")
            if not image_data:
                continue

            img_bytes = base64.b64decode(image_data)
            img_tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            img_tmp.write(img_bytes)
            img_tmp.close()

            output_dir = tempfile.mkdtemp()

            try:
                verdict = detect_cherry_picking(img_tmp.name, dataset_tmp.name, output_dir)
                if verdict["score"] > worst_score:
                    worst_score = verdict["score"]
                    result["severity"] = verdict["severity"]
                    result["cherry_findings"] = [
                        {"type": f["type"], "detail": f["detail"], "impact": f["impact_score"]}
                        for f in verdict.get("cherry_findings", [])
                    ]
                    result["legitimate_aspects"] = [
                        {"type": f["type"], "detail": f["detail"]}
                        for f in verdict.get("legitimate_aspects", [])
                    ]
                    result["mitigating_factors"] = verdict.get("mitigating_factors", [])
            except Exception as e:
                result["errors"].append(f"Cherry pick analysis failed on chart: {str(e)[:100]}")
            finally:
                os.unlink(img_tmp.name)
                import shutil
                shutil.rmtree(output_dir, ignore_errors=True)

        result["score"] = worst_score
        os.unlink(dataset_tmp.name)

    except Exception as e:
        result["errors"].append(f"Cherry picking setup failed: {str(e)[:150]}")

    return result


def evaluate_graph_misleading(visual_assets: list[dict]) -> dict:
    """Run misleading graph detection on chart images using ChartGemma.

    Returns:
        Dict with: score (0-10, higher = more misleading), verdict, per_chart details, errors.
    """
    result = {
        "score": 0.0,
        "verdict": "Not misleading",
        "per_chart": [],
        "errors": [],
    }

    chart_assets = [a for a in visual_assets if a.get("type") == "chart"]
    if not chart_assets:
        result["errors"].append("No chart images found in PDF")
        return result

    try:
        # Add misleading_graph2 to path
        graph_dir = os.path.join(PROJECT_ROOT, "misleading_graph2")
        if graph_dir not in sys.path:
            sys.path.insert(0, graph_dir)

        from api import ChartAnalyzer
        analyzer = ChartAnalyzer(device="cpu")

        worst_score = 0.0
        for chart in chart_assets[:4]:  # Limit to 4 charts
            image_data = chart.get("image_data", "")
            if not image_data:
                continue

            img_bytes = base64.b64decode(image_data)
            img_tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            img_tmp.write(img_bytes)
            img_tmp.close()

            try:
                chart_result = analyzer.analyze_single(img_tmp.name)
                score = chart_result.get("overall_score") or 0.0
                if score > worst_score:
                    worst_score = score
                    result["verdict"] = chart_result.get("overall_verdict", "Unknown")

                result["per_chart"].append({
                    "page_number": chart.get("page_number"),
                    "score": score,
                    "verdict": chart_result.get("overall_verdict", "Unknown"),
                    "issues": [
                        issue
                        for c in chart_result.get("per_chart", [])
                        for issue in (c.get("detected_issues") or [])
                    ][:5],
                })
            except Exception as e:
                result["errors"].append(f"Graph analysis failed: {str(e)[:100]}")
            finally:
                os.unlink(img_tmp.name)

        result["score"] = worst_score

    except Exception as e:
        result["errors"].append(f"Graph analyzer setup failed: {str(e)[:150]}")

    return result


def run_evaluation(paper_id: str) -> None:
    """Run all evaluation modules on a parsed paper.

    Reads visual_assets and metadata from the store, runs evaluations,
    and stores results back.
    """
    from app.store import get_entry, update_entry

    entry = get_entry(paper_id)
    if entry is None:
        return

    update_entry(paper_id, current_step="Running AI image detection...")

    # Evaluate images for AI generation
    visual_assets = entry.get("visual_assets", [])
    try:
        image_eval = evaluate_images(visual_assets)
        update_entry(paper_id, image_evaluation=image_eval)
    except Exception:
        update_entry(paper_id, image_evaluation=[])

    update_entry(paper_id, current_step="Checking journal credibility (predatory list, MNCS)...")

    # Evaluate metadata (predatory check + MNCS)
    metadata = entry.get("metadata")
    try:
        metadata_eval = evaluate_metadata(metadata)
        update_entry(paper_id, metadata_evaluation=metadata_eval)
    except Exception:
        update_entry(paper_id, metadata_evaluation={})

    update_entry(paper_id, current_step="Running cherry picking detection...")

    # Evaluate cherry picking (charts vs dataset)
    datasets = entry.get("datasets", [])
    try:
        cherry_eval = evaluate_cherry_picking(visual_assets, datasets)
        update_entry(paper_id, cherry_picking_evaluation=cherry_eval)
    except Exception:
        update_entry(paper_id, cherry_picking_evaluation={})

    update_entry(paper_id, current_step="Computing lie factor...")

    # Evaluate lie factor (charts vs dataset)
    try:
        lie_eval = evaluate_lie_factor(visual_assets, datasets)
        update_entry(paper_id, lie_factor_evaluation=lie_eval)
    except Exception:
        update_entry(paper_id, lie_factor_evaluation={})

    update_entry(paper_id, current_step="Analyzing graphs for misleading patterns...")

    # Evaluate misleading graphs
    try:
        graph_eval = evaluate_graph_misleading(visual_assets)
        update_entry(paper_id, graph_evaluation=graph_eval)
    except Exception:
        update_entry(paper_id, graph_evaluation={})
