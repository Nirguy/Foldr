"""
Misleading Graph Detection using ChartGemma (ahmed-masry/chartgemma).

API:
    from llava_analyzer import analyze
    results = analyze(["path/to/image1.png", "path/to/image2.jpg"])

Each result is a dict:
    {
        "file": "path/to/image.png",
        "score": 6.5,
        "severity": "medium",   # "low" (0-3), "medium" (4-7), "high" (8-10)
        "reason": "..."         # only included for medium/high
    }
"""

import sys
import re
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import torch
from PIL import Image
from transformers import AutoProcessor, PaliGemmaForConditionalGeneration


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL_ID = "ahmed-masry/chartgemma"
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp"}

PROMPT = (
    "What misleading or deceptive techniques are used in this chart? "
    "Describe any problems with the axes, proportions, data selection, "
    "title, colors, or chart type that could mislead a viewer."
)

# ---------------------------------------------------------------------------
# Model (lazy-loaded singleton)
# ---------------------------------------------------------------------------

_model = None
_processor = None


def _load_model():
    global _model, _processor
    if _model is not None:
        return

    print("Loading ChartGemma model...")
    _model = PaliGemmaForConditionalGeneration.from_pretrained(
        MODEL_ID, torch_dtype=torch.float32
    )
    _model.eval()
    _processor = AutoProcessor.from_pretrained(MODEL_ID)
    print("Model loaded.")


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def _run_inference(image: Image.Image, max_new_tokens: int = 150) -> str:
    _load_model()

    # Resize for speed
    if max(image.size) > 800:
        image.thumbnail((800, 800), Image.LANCZOS)

    prompt = f"<image> {PROMPT}"
    inputs = _processor(text=prompt, images=image, return_tensors="pt")
    prompt_len = inputs["input_ids"].shape[1]

    with torch.no_grad():
        output_ids = _model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)

    generated = output_ids[0][prompt_len:]
    return _processor.tokenizer.decode(generated, skip_special_tokens=True).strip()


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _compute_score(text: str) -> float:
    """Compute misleading score 0-10 from model response."""
    text_lower = text.lower()

    # Try to find explicit score in response
    for pattern in [r"SCORE:\s*(\d+(?:\.\d+)?)\s*/\s*10",
                    r"(\d+(?:\.\d+)?)\s*/\s*10",
                    r"score[:\s]+(\d+(?:\.\d+)?)"]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            score = float(match.group(1))
            if 0 <= score <= 10:
                return score

    # Keyword-based estimation
    strong = ["truncated", "manipulative", "distorted", "cherry-picked",
              "deceptive", "sensationalized", "biased", "skewed", "hidden",
              "does not start at zero", "not start at zero",
              "misleading title", "false correlation", "axis break",
              "cut off", "inverted", "exaggerated scales"]

    mild = ["misleading", "limited range", "not show absolute",
            "inappropriate", "inconsistent", "missing data",
            "incomplete", "omitted"]

    complexity = ["overly complex", "many lines", "overlapping",
                  "limited range of colors", "visual confusion",
                  "unnecessary labels", "could discourage", "could lead to"]

    positive = ["accurate", "honest", "appropriate", "clear", "not misleading",
                "no issues", "well-designed", "fair representation",
                "no deceptive", "no problems", "concise design", "straightforward"]

    s = sum(1 for kw in strong if kw in text_lower) * 2.5
    s += sum(1 for kw in mild if kw in text_lower) * 1.0
    s -= sum(1 for kw in complexity if kw in text_lower) * 1.5
    s -= sum(1 for kw in positive if kw in text_lower) * 2.0

    return round(max(0.0, min(10.0, s)), 1)


def _get_severity(score: float) -> str:
    if score <= 3:
        return "low"
    elif score <= 7:
        return "medium"
    else:
        return "high"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze(image_paths: list) -> list:
    """
    Analyze images for misleading graph design.

    Args:
        image_paths: List of file paths (str or Path) to chart images.

    Returns:
        List of dicts with keys: file, score, severity, reason (if medium/high).
    """
    _load_model()
    results = []

    for path in image_paths:
        path = Path(path)
        entry = {"file": str(path), "score": 0.0, "severity": "low"}

        if not path.exists():
            entry["score"] = 0.0
            entry["severity"] = "low"
            entry["reason"] = "File not found"
            results.append(entry)
            continue

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            results.append(entry)
            continue

        try:
            image = Image.open(path).convert("RGB")
            response = _run_inference(image)
            score = _compute_score(response)
            severity = _get_severity(score)

            entry["score"] = score
            entry["severity"] = severity

            # Include reason only for medium/high
            if severity in ("medium", "high"):
                entry["reason"] = response

        except Exception as e:
            entry["reason"] = f"Error: {e}"

        results.append(entry)

    return results


# ---------------------------------------------------------------------------
# CLI (optional standalone usage)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Misleading graph detector.")
    parser.add_argument("inputs", nargs="+", help="Image file(s) or folder(s).")
    parser.add_argument("--output", "-o", help="Save JSON results to file.")
    args = parser.parse_args()

    # Expand folders
    paths = []
    for p in args.inputs:
        p = Path(p)
        if p.is_dir():
            paths.extend(sorted(f for f in p.iterdir() if f.suffix.lower() in SUPPORTED_EXTENSIONS))
        elif p.is_file():
            paths.append(p)

    if not paths:
        print("No images found.")
        sys.exit(1)

    print(f"Analyzing {len(paths)} image(s)...\n")
    results = analyze(paths)

    # Print results
    for r in results:
        severity_tag = {"low": "[LOW]", "medium": "[MEDIUM]", "high": "[HIGH]"}[r["severity"]]
        print(f"  {severity_tag} {r['score']}/10  {Path(r['file']).name}")
        if "reason" in r and r["severity"] != "low":
            print(f"         Reason: {r['reason'][:150]}")
        print()

    # Save if requested
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Saved to: {args.output}")
