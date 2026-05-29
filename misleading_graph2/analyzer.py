"""
Chart Misleading Detection using ChartGemma (ahmed-masry/chartgemma)
Optimized with OpenVINO GPU acceleration + greedy decoding + single prompt.

Speedups applied:
  1. OpenVINO backend on GPU (or NPU/CPU fallback)
  2. Greedy decoding (num_beams=1) instead of beam search
  3. Reduced max_new_tokens (200 instead of 400)
  4. Single combined prompt (no separate score prompt)
  5. INT8/FP16 weight compression via OpenVINO
"""

import re
import sys
import json
import argparse
from pathlib import Path

# Ensure stdout handles all characters on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import torch
from PIL import Image
from tqdm import tqdm


# ---------------------------------------------------------------------------
# Graph splitting (from crop_charts.py logic, simplified)
# ---------------------------------------------------------------------------

def split_into_charts(image: Image.Image) -> list:
    """Detect and crop individual chart regions from a composite image."""
    try:
        import numpy as np
        import cv2
    except ImportError:
        return [image]

    img_np = np.array(image.convert("RGB"))
    h, w = img_np.shape[:2]
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

    dark_mask = gray < 200
    row_dark = dark_mask.sum(axis=1).astype(float)
    col_dark = dark_mask.sum(axis=0).astype(float)

    kernel = np.ones(5) / 5
    row_dark = np.convolve(row_dark, kernel, mode='same')
    col_dark = np.convolve(col_dark, kernel, mode='same')

    row_thresh = max(2, row_dark.max() * 0.01)
    col_thresh = max(2, col_dark.max() * 0.01)

    def find_cuts(profile, total, thresh, min_band=12, min_cell_frac=0.10):
        is_empty = profile <= thresh
        bands = []
        in_band = False
        start = 0
        for i in range(total):
            if is_empty[i] and not in_band:
                in_band = True
                start = i
            elif not is_empty[i] and in_band:
                in_band = False
                if i - start >= min_band:
                    bands.append((start + i) // 2)
        if in_band and total - start >= min_band:
            bands.append((start + total) // 2)
        min_cell = int(total * min_cell_frac)
        filtered = []
        prev = 0
        for c in sorted(bands):
            if c - prev >= min_cell and total - c >= min_cell:
                filtered.append(c)
                prev = c
        return filtered

    h_cuts = find_cuts(row_dark, h, row_thresh)
    v_cuts = find_cuts(col_dark, w, col_thresh)

    h_edges = [0] + h_cuts + [h]
    v_edges = [0] + v_cuts + [w]

    crops = []
    for r in range(len(h_edges) - 1):
        for c in range(len(v_edges) - 1):
            y1, y2 = h_edges[r], h_edges[r + 1]
            x1, x2 = v_edges[c], v_edges[c + 1]
            cell_h, cell_w = y2 - y1, x2 - x1
            if cell_h < h * 0.08 or cell_w < w * 0.08:
                continue
            # Check dark content ratio
            cell_gray = gray[y1:y2, x1:x2]
            dark_ratio = (cell_gray < 200).sum() / (cell_h * cell_w)
            if dark_ratio < 0.02:
                continue
            crops.append(image.crop((x1, y1, x2, y2)))

    if not crops:
        crops = [image]
    return crops


# ---------------------------------------------------------------------------
# Model loading — OpenVINO optimized
# ---------------------------------------------------------------------------

MODEL_ID = "ahmed-masry/chartgemma"

PROMPT = (
    "<image> Is this chart misleading or manipulative? "
    "Check for: truncated axes, distorted proportions, dual axes, "
    "cherry-picked data, misleading labels, omitted data, "
    "inappropriate chart type, misleading title. "
    "Rate it 0-10 where 0=honest and 10=highly manipulative. "
    "List issues found."
)


def load_model(device: str = "auto"):
    """Load ChartGemma with OpenVINO backend for GPU/NPU acceleration."""
    from transformers import AutoProcessor

    # Determine best device
    if device == "auto":
        try:
            import openvino as ov
            core = ov.Core()
            available = core.available_devices
            if "GPU" in available:
                device = "GPU"
            elif "NPU" in available:
                device = "NPU"
            else:
                device = "CPU"
        except Exception:
            device = "CPU"

    print(f"Loading ChartGemma from '{MODEL_ID}' with OpenVINO on {device} ...")

    try:
        from optimum.intel import OVModelForVision2Seq

        model = OVModelForVision2Seq.from_pretrained(
            MODEL_ID,
            export=True,
            device=device,
            compile=True,
        )
        processor = AutoProcessor.from_pretrained(MODEL_ID, use_fast=True)
        backend = f"OpenVINO ({device})"
    except Exception as e:
        print(f"  OpenVINO failed ({e}), falling back to PyTorch CPU ...")
        from transformers import PaliGemmaForConditionalGeneration
        model = PaliGemmaForConditionalGeneration.from_pretrained(
            MODEL_ID, dtype=torch.float32
        )
        model = model.to("cpu")
        model.eval()
        processor = AutoProcessor.from_pretrained(MODEL_ID, use_fast=True)
        backend = "PyTorch (CPU)"
        device = "cpu"

    print(f"Model loaded: {backend}\n")
    return model, processor, device


# ---------------------------------------------------------------------------
# Inference — single fast prompt, greedy decoding
# ---------------------------------------------------------------------------

def _run_inference(image: Image.Image, model, processor, device: str) -> str:
    """Run single prompt with greedy decoding and short output."""
    inputs = processor(
        text=PROMPT,
        images=image,
        return_tensors="pt",
    )
    prompt_length = inputs["input_ids"].shape[1]

    # Move to device if PyTorch
    if device == "cpu":
        inputs = {k: v.to("cpu") for k, v in inputs.items()}

    with torch.no_grad():
        generate_ids = model.generate(
            **inputs,
            max_new_tokens=200,
            do_sample=False,
        )

    new_tokens = generate_ids[0][prompt_length:]
    if hasattr(processor, 'tokenizer'):
        output = processor.tokenizer.decode(new_tokens, skip_special_tokens=True)
    else:
        output = processor.decode(new_tokens, skip_special_tokens=True)
    return output.strip()


# ---------------------------------------------------------------------------
# Per-chart analysis
# ---------------------------------------------------------------------------

def analyze_single_crop(crop: Image.Image, chart_index: int,
                        model, processor, device: str) -> dict:
    result = {
        "chart_index": chart_index,
        "verdict": None,
        "score": None,
        "score_normalized": None,
        "detected_issues": [],
        "explanation": None,
        "recommendation": None,
        "raw_output": None,
        "error": None,
    }

    try:
        text = _run_inference(crop, model, processor, device)
    except Exception as exc:
        result["error"] = f"Inference failed: {exc}"
        return result

    result["raw_output"] = text

    # Parse score from output
    score_match = re.search(r"\b(10(?:\.0+)?|[0-9](?:\.[0-9]+)?)\b", text)
    if score_match:
        raw_score = float(score_match.group(1))
        result["score"] = raw_score
        result["score_normalized"] = round(raw_score / 10.0, 2)
    else:
        result["score"], result["score_normalized"] = _infer_score(text)

    result["verdict"] = _score_to_verdict(result["score"])
    result["detected_issues"] = _extract_issues(text)
    result["explanation"] = text
    result["recommendation"] = _build_recommendation(result["score"], result["detected_issues"])

    return result


def _infer_score(text: str) -> tuple:
    text_lower = text.lower()
    neg_kw = ["truncated", "misleading", "manipulative", "distorted", "cherry",
              "omitted", "hidden", "exaggerat", "deceptive", "false", "incorrect",
              "inaccurate", "bias", "skewed", "inflated"]
    pos_kw = ["accurate", "honest", "correct", "clear", "not misleading",
              "no issues", "properly", "appropriate", "fair"]
    neg = sum(1 for kw in neg_kw if kw in text_lower)
    pos = sum(1 for kw in pos_kw if kw in text_lower)
    raw = max(0.0, min(10.0, neg * 1.2 - pos * 0.5))
    return round(raw, 1), round(raw / 10.0, 2)


def _score_to_verdict(score) -> str:
    if score is None:
        return "Unknown"
    if score <= 2.5:
        return "Not Misleading"
    if score <= 5.5:
        return "Possibly Misleading"
    return "Misleading"


def _extract_issues(text: str) -> list:
    issues = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r'^[-*]|^\d+[.)]\s', stripped):
            clean = re.sub(r'^[-*\d.)]+\s*', '', stripped).strip()
            if len(clean) > 10:
                issues.append(clean)
    if not issues:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        keywords = ["truncated", "misleading", "distorted", "cherry", "omitted",
                    "exaggerat", "deceptive", "incorrect", "inaccurate", "bias"]
        for sent in sentences:
            if any(kw in sent.lower() for kw in keywords):
                issues.append(sent.strip())
    return issues


def _build_recommendation(score, issues: list) -> str:
    if score is None or score <= 2.5:
        return "This chart appears to be an honest representation of the data."
    if issues:
        return ("Pay attention to: " + "; ".join(issues[:2]) + ".")
    return "Verify the axis ranges and data source before accepting conclusions."


# ---------------------------------------------------------------------------
# Batch processing with live output
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp"}


def collect_images(paths: list) -> list:
    images = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            for child in sorted(path.iterdir()):
                if child.suffix.lower() in SUPPORTED_EXTENSIONS:
                    images.append(child)
        elif path.is_file():
            if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                images.append(path)
            else:
                print(f"[WARN] Skipping: {path}")
        else:
            print(f"[WARN] Not found: {path}")
    return images


VERDICT_TAG = {
    "not misleading": "[OK]",
    "possibly misleading": "[WARN]",
    "misleading": "[ALERT]",
    "unknown": "[?]",
}


def _verdict_tag(verdict: str) -> str:
    for key, tag in VERDICT_TAG.items():
        if key in (verdict or "").lower():
            return tag
    return "[?]"


def analyze_batch(image_paths: list, model, processor, device: str) -> list:
    results = []
    total_files = len(image_paths)

    for file_idx, img_path in enumerate(image_paths, 1):
        fname = Path(img_path).name
        print(f"\n{'='*70}", flush=True)
        print(f"  IMAGE {file_idx}/{total_files}: {fname}", flush=True)
        print(f"{'='*70}", flush=True)

        file_result = {
            "file": str(img_path),
            "num_charts_detected": 0,
            "overall_verdict": None,
            "overall_score": None,
            "overall_score_normalized": None,
            "per_chart": [],
            "error": None,
        }

        try:
            image = Image.open(img_path).convert("RGB")
        except Exception as exc:
            file_result["error"] = f"Could not open image: {exc}"
            print(f"  ERROR: {exc}", flush=True)
            results.append(file_result)
            continue

        crops = split_into_charts(image)
        file_result["num_charts_detected"] = len(crops)
        print(f"  Detected {len(crops)} chart(s)\n", flush=True)

        for i, crop in enumerate(crops):
            print(f"  Analyzing chart {i+1}/{len(crops)} ...", flush=True)
            chart_result = analyze_single_crop(crop, chart_index=i + 1,
                                               model=model, processor=processor,
                                               device=device)
            file_result["per_chart"].append(chart_result)

            # Print immediately
            c = chart_result
            tag = _verdict_tag(c["verdict"] or "")
            score_str = f"{c['score']:.1f}/10" if c["score"] is not None else "N/A"
            print(f"\n  {'-'*60}", flush=True)
            print(f"  CHART {i+1}/{len(crops)}: {tag} {c['verdict']}  Score: {score_str}", flush=True)
            if c["error"]:
                print(f"  ERROR: {c['error']}", flush=True)
            elif c["detected_issues"]:
                for issue in c["detected_issues"][:3]:
                    print(f"    - {issue}", flush=True)
            if c["explanation"]:
                lines = c["explanation"].splitlines()
                for line in lines[:3]:
                    if line.strip():
                        print(f"    {line.strip()}", flush=True)
            print(flush=True)

        # Aggregate
        scores = [c["score"] for c in file_result["per_chart"] if c["score"] is not None]
        if scores:
            overall = max(scores)
            file_result["overall_score"] = overall
            file_result["overall_score_normalized"] = round(overall / 10.0, 2)
            file_result["overall_verdict"] = _score_to_verdict(overall)
        else:
            file_result["overall_verdict"] = "Unknown"

        print(f"  --- Image result: {file_result['overall_verdict']} "
              f"(worst: {file_result['overall_score']}/10) ---", flush=True)
        results.append(file_result)

    return results


# ---------------------------------------------------------------------------
# Summary + save
# ---------------------------------------------------------------------------

def print_summary(results: list) -> None:
    print(f"\n{'='*70}")
    print("  SUMMARY")
    print(f"{'='*70}")
    print(f"  {'File':<35} {'Verdict':<22} {'Score':>6}  {'Charts':>6}")
    print(f"  {'-'*35} {'-'*22} {'-'*6}  {'-'*6}")
    for r in results:
        name = Path(r["file"]).name[:34]
        if r["error"]:
            print(f"  {name:<35} {'ERROR':<22} {'N/A':>6}  {'N/A':>6}")
        else:
            verdict = (r["overall_verdict"] or "Unknown")[:21]
            score = f"{r['overall_score']:.1f}" if r["overall_score"] is not None else "N/A"
            charts = str(r["num_charts_detected"])
            print(f"  {name:<35} {verdict:<22} {score:>6}  {charts:>6}")
    print(f"{'='*70}\n")


def save_json(results: list, output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Results saved to: {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Detect misleading charts using ChartGemma + OpenVINO.",
    )
    parser.add_argument("inputs", nargs="+", help="Image file(s) or folder(s).")
    parser.add_argument("--output", "-o", default=None, help="Save JSON results.")
    parser.add_argument("--device", default="auto", choices=["auto", "GPU", "NPU", "CPU", "cpu"])
    parser.add_argument("--json-only", action="store_true")
    args = parser.parse_args()

    image_paths = collect_images(args.inputs)
    if not image_paths:
        print("No supported image files found.")
        sys.exit(1)

    print(f"Found {len(image_paths)} image file(s) to analyze.\n")

    model, processor, device = load_model(args.device)
    results = analyze_batch(image_paths, model, processor, device)

    if args.json_only:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print_summary(results)

    if args.output:
        save_json(results, args.output)


if __name__ == "__main__":
    main()
