"""
Cherry-Pick Detector v2 — Context-Aware
========================================
Key principle: A focused graph is NOT cherry-picking.
Cherry-picking requires that hidden data CONTRADICTS the shown conclusion.

Scoring (0-100):
  0-20:  Legitimate focused presentation
  21-40: Minor concerns, not misleading
  41-60: Moderate — some misleading framing
  61-80: High — hidden data contradicts shown narrative
  81-100: Extreme — actively deceptive

Checks performed:
  1. Does hidden data CONTRADICT the shown trend/conclusion?
  2. Is the y-axis scaled to DISTORT perception (not just focused)?
  3. Does the title/framing make UNSUPPORTED claims?
  4. Are statistical results selectively reported?
  5. Is the sample size adequate for the claims made?
"""

import os
import sys
import re
import json
import numpy as np
import pandas as pd
import cv2
import easyocr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

# ── Lazy OCR ─────────────────────────────────────────────────────────────────
_ocr_reader = None
def get_ocr():
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        print("  [OCR] Loading EasyOCR…")
        _ocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _ocr_reader


def load_dataset(path: str) -> pd.DataFrame:
    ext = Path(path).suffix.lower()
    if ext == ".csv":
        return pd.read_csv(path)
    elif ext in (".xls", ".xlsx"):
        return pd.read_excel(path)
    elif ext == ".json":
        return pd.read_json(path)
    raise ValueError(f"Unsupported: {ext}")


# ══════════════════════════════════════════════════════════════════════════════
# DETECTOR CLASS
# ══════════════════════════════════════════════════════════════════════════════

class CherryPickDetector:
    def __init__(self):
        self.findings = []
        self.mitigating = []

    def add_finding(self, ftype, detail, is_cherry_pick, impact, justification):
        self.findings.append({
            "type": ftype,
            "detail": detail,
            "is_cherry_pick": is_cherry_pick,
            "impact_score": max(0, min(100, impact)),
            "justification": justification,
        })

    def add_mitigating(self, factor):
        self.mitigating.append(factor)

    def get_verdict(self):
        cherry = [f for f in self.findings if f["is_cherry_pick"]]
        legit = [f for f in self.findings if not f["is_cherry_pick"]]

        if not cherry:
            score = 0
        else:
            score = int(np.mean([f["impact_score"] for f in cherry]))

        # Mitigating factors reduce score (max -30)
        score = max(0, score - min(len(self.mitigating) * 10, 30))

        if score <= 20:
            severity = "None/Minimal"
        elif score <= 40:
            severity = "Low"
        elif score <= 60:
            severity = "Medium"
        elif score <= 80:
            severity = "High"
        else:
            severity = "Extreme"

        return {
            "score": score,
            "severity": severity,
            "cherry_findings": cherry,
            "legitimate_aspects": legit,
            "mitigating_factors": self.mitigating,
        }

# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS CHECKS
# ══════════════════════════════════════════════════════════════════════════════

def check_range_selection(det, df, x_col, shown_min, shown_max):
    """
    Check if showing a time/x subset is cherry-picking.
    Only flags if hidden data CONTRADICTS the shown pattern.
    """
    if x_col not in df.columns:
        return

    x_vals = pd.to_numeric(df[x_col], errors="coerce").dropna()
    full_min, full_max = float(x_vals.min()), float(x_vals.max())
    full_range = full_max - full_min
    shown_range = shown_max - shown_min
    pct = (shown_range / full_range * 100) if full_range > 0 else 100

    if pct >= 80:
        det.add_mitigating("Most of the data range is shown (≥80%)")
        return

    # Check each numeric column for contradictions
    shown_mask = (x_vals >= shown_min) & (x_vals <= shown_max)
    numeric_cols = [c for c in df.select_dtypes(include=[np.number]).columns if c != x_col]

    contradictions = []
    consistent = []

    for col in numeric_cols:
        vals = pd.to_numeric(df[col], errors="coerce")
        shown_vals = vals[shown_mask].dropna()
        hidden_vals = vals[~shown_mask].dropna()

        if len(shown_vals) < 3 or len(hidden_vals) < 3:
            continue

        # Trend comparison
        shown_slope = np.polyfit(range(len(shown_vals)), shown_vals.values, 1)[0]
        hidden_slope = np.polyfit(range(len(hidden_vals)), hidden_vals.values, 1)[0]

        # Mean comparison
        mean_diff = abs(shown_vals.mean() - hidden_vals.mean())
        pooled_std = np.sqrt((shown_vals.std()**2 + hidden_vals.std()**2) / 2)

        # Contradiction: opposite trend AND meaningful magnitude
        if (shown_slope > 0) != (hidden_slope > 0) and \
           abs(hidden_slope) > abs(shown_slope) * 0.3 and \
           pooled_std > 0:
            contradictions.append((col, shown_slope, hidden_slope))
        # Significant mean difference (effect size > 0.5)
        elif pooled_std > 0 and mean_diff / pooled_std > 0.5:
            contradictions.append((col, shown_vals.mean(), hidden_vals.mean()))
        else:
            consistent.append(col)

    if contradictions:
        det.add_finding(
            "CONTRADICTING DATA HIDDEN",
            f"Only {pct:.0f}% of x-range shown ({shown_min:.1f}–{shown_max:.1f}). "
            f"Hidden data contradicts shown pattern in: "
            f"{', '.join(c[0] for c in contradictions)}.",
            is_cherry_pick=True,
            impact=60 + min(len(contradictions) * 10, 30),
            justification="Hidden data would change the viewer's conclusion."
        )
    elif pct < 30:
        det.add_finding(
            "NARROW RANGE SHOWN",
            f"Only {pct:.0f}% of data range shown, but hidden data is "
            f"consistent with shown pattern.",
            is_cherry_pick=False,
            impact=10,
            justification="Narrow view, but hidden data doesn't contradict. "
                          "Likely a legitimate focused figure."
        )
        det.add_mitigating("Hidden data is consistent with shown data")
    else:
        det.add_mitigating(f"Shown range ({pct:.0f}%) has consistent hidden data")


def check_yaxis_manipulation(det, shown_y_min, shown_y_max, data_min, data_max):
    """
    Check if y-axis scaling is misleading.

    NOT misleading if:
      - Y-axis is appropriately scaled for the data being shown
      - Starting above zero is standard for the data type (e.g., temperatures)

    IS misleading if:
      - Y-axis is zoomed to make small changes look large
      - The zoom hides that the effect is tiny relative to the baseline
    """
    if data_max <= data_min:
        return

    data_range = data_max - data_min
    shown_range = shown_y_max - shown_y_min

    # Check if y starts far from zero when zero is meaningful
    starts_above_zero = shown_y_min > data_range * 0.1

    # Zoom ratio: how much of the data range is shown
    zoom_ratio = shown_range / data_range if data_range > 0 else 1.0

    if starts_above_zero and zoom_ratio < 0.3:
        # Extreme zoom — but is it misleading?
        # It's misleading if the actual variation is tiny relative to the values
        relative_variation = data_range / abs(data_max) if data_max != 0 else 1.0

        if relative_variation < 0.1:
            # The variation is <10% of the values — zooming exaggerates
            det.add_finding(
                "Y-AXIS ZOOM EXAGGERATES VARIATION",
                f"Y-axis shows {shown_y_min:.2f}–{shown_y_max:.2f} "
                f"(data varies by only {relative_variation*100:.1f}% of its magnitude). "
                f"The zoom makes small changes appear dramatic.",
                is_cherry_pick=True,
                impact=55,
                justification="Zoomed axis makes trivial variation look significant."
            )
        else:
            det.add_finding(
                "Y-AXIS FOCUSED RANGE",
                f"Y-axis doesn't start at zero ({shown_y_min:.2f}–{shown_y_max:.2f}), "
                f"but variation is {relative_variation*100:.1f}% of magnitude — "
                f"appropriate scaling for this data.",
                is_cherry_pick=False,
                impact=0,
                justification="Starting above zero is appropriate when variation is meaningful."
            )
            det.add_mitigating("Y-axis scaling is appropriate for the data range")
    elif starts_above_zero:
        det.add_mitigating("Y-axis focused but not exaggerating")


def check_hidden_columns(det, df, shown_cols, all_numeric_cols):
    """
    Check if hidden columns contradict the shown ones.

    NOT cherry-picking if:
      - Hidden columns show the same pattern
      - The graph is focused on a specific measurement (normal in science)

    IS cherry-picking if:
      - Hidden columns show opposite trends
      - A key related metric (e.g., profit when showing revenue) is hidden
    """
    hidden_cols = [c for c in all_numeric_cols if c not in shown_cols]
    if not hidden_cols:
        return

    # Check correlation between shown and hidden columns
    contradicting = []
    for shown_col in shown_cols:
        if shown_col not in df.columns:
            continue
        shown_data = pd.to_numeric(df[shown_col], errors="coerce").dropna()
        if len(shown_data) < 3:
            continue

        shown_trend = np.polyfit(range(len(shown_data)), shown_data.values, 1)[0]

        for hidden_col in hidden_cols:
            hidden_data = pd.to_numeric(df[hidden_col], errors="coerce").dropna()
            if len(hidden_data) < 3:
                continue
            hidden_trend = np.polyfit(range(len(hidden_data)), hidden_data.values, 1)[0]

            # Strong contradiction: opposite direction with meaningful magnitude
            if (shown_trend > 0) != (hidden_trend > 0) and \
               abs(hidden_trend) > abs(shown_trend) * 0.5:
                contradicting.append((hidden_col, hidden_trend))

    if contradicting:
        det.add_finding(
            "CONTRADICTING COLUMNS HIDDEN",
            f"Hidden columns show opposite trends: "
            f"{', '.join(f'{c} (slope={s:.4f})' for c, s in contradicting)}. "
            f"These would change the viewer's conclusion.",
            is_cherry_pick=True,
            impact=65,
            justification="Related data with opposite trends is hidden."
        )
    else:
        det.add_finding(
            "FOCUSED COLUMN SELECTION",
            f"Graph shows {shown_cols}. Other columns exist ({hidden_cols}) "
            f"but don't contradict the shown pattern.",
            is_cherry_pick=False,
            impact=0,
            justification="Showing specific columns is standard scientific practice. "
                          "Hidden columns are consistent."
        )
        det.add_mitigating("Hidden columns don't contradict shown data")


def check_sample_size(det, n_values: dict):
    """
    Flag sample size issues only if they affect reliability of shown claims.
    Small n is common in animal studies and isn't cherry-picking by itself.
    """
    min_n = min(n_values.values()) if n_values else 0
    max_n = max(n_values.values()) if n_values else 0

    if min_n < 3:
        det.add_finding(
            "VERY LOW SAMPLE SIZE",
            f"Some conditions have n<3, making statistical claims unreliable.",
            is_cherry_pick=False,  # Low n isn't cherry-picking, it's a limitation
            impact=0,
            justification="Small sample size is a study limitation, not cherry-picking. "
                          "Common in animal neuroscience studies."
        )
    elif min_n < 6 and max_n > min_n * 3:
        det.add_finding(
            "UNEQUAL SAMPLE SIZES",
            f"Sample sizes range from {min_n} to {max_n}. Large variation may "
            f"indicate data exclusion, but could also reflect experimental constraints.",
            is_cherry_pick=False,
            impact=10,
            justification="Variable n is common when some conditions are harder to measure. "
                          "Not evidence of cherry-picking without additional context."
        )
        det.add_mitigating("Variable sample sizes are noted (transparent reporting)")


def check_statistical_selectivity(det, p_values: dict):
    """
    Check if only significant results are shown.
    Only flags if non-significant results CONTRADICT the narrative.
    """
    sig = {k: v for k, v in p_values.items() if v <= 0.05}
    nonsig = {k: v for k, v in p_values.items() if v > 0.05}

    if not nonsig:
        det.add_mitigating("All reported statistical tests are significant")
        return

    if sig and nonsig:
        # Having both significant and non-significant results is TRANSPARENT
        det.add_finding(
            "MIXED STATISTICAL RESULTS",
            f"Dataset contains both significant ({list(sig.keys())}) and "
            f"non-significant ({list(nonsig.keys())}) results.",
            is_cherry_pick=False,
            impact=0,
            justification="Reporting both significant and non-significant results "
                          "is transparent, not cherry-picking."
        )
        det.add_mitigating("Both significant and non-significant results are in the data")

def check_selective_data_points(det, df, graph_info, ocr_texts):
    """
    Check if only a subset of data points are plotted (scatter/point selection).

    This is the Ancel Keys type of cherry-picking: you have 22 countries but
    only plot 6 that support your hypothesis.

    IS cherry-picking if:
      - The graph shows far fewer points than the dataset has rows
      - The shown points create a stronger correlation than the full dataset
      - The hidden points would weaken or break the apparent pattern
    """
    # Count data points visible in graph (from colored regions / scatter dots)
    img = cv2.imread(graph_info.get("_image_path", ""))
    if img is None:
        return

    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Find scatter points: small colored regions
    colored = cv2.inRange(hsv, (0, 30, 30), (180, 255, 240))
    colored[gray < 50] = 0   # remove axes/text
    colored[gray > 240] = 0  # remove white background

    contours, _ = cv2.findContours(colored, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # Filter to reasonable point sizes (not too large = bars/legends)
    point_areas = [cv2.contourArea(c) for c in contours]
    # Points can be very small (1-5px area) in scatter plots
    reasonable_points = [a for a in point_areas if a >= 0 and a < 2000]
    n_points_in_graph = len(reasonable_points)

    n_rows_in_data = len(df)

    if n_rows_in_data <= 3 or n_points_in_graph == 0:
        return

    # Also check OCR for country/label names that match dataset
    dataset_labels = set()
    for col in df.columns:
        if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
            dataset_labels.update(str(v).lower().strip() for v in df[col].dropna())

    ocr_label_texts = [t[0].lower().strip() for t in ocr_texts if len(t) > 1 and (t[1] if isinstance(t[1], (int, float)) else 0.5) > 0.5]
    matched_labels = []
    for ocr_text in ocr_label_texts:
        for dl in dataset_labels:
            if len(dl) > 2 and (dl in ocr_text or ocr_text in dl):
                matched_labels.append(ocr_text)
                break

    # Use matched labels count if available, otherwise use point count
    n_shown = max(len(matched_labels), n_points_in_graph)
    if len(matched_labels) >= 3:
        n_shown = len(matched_labels)  # trust label matching more

    pct_shown = (n_shown / n_rows_in_data * 100) if n_rows_in_data > 0 else 100

    if pct_shown >= 70:
        return  # most data is shown

    # Check if the shown subset creates a stronger pattern than the full data
    numeric_cols = list(df.select_dtypes(include=[np.number]).columns)
    if len(numeric_cols) >= 2:
        x_col, y_col = numeric_cols[0], numeric_cols[1]
        x_full = pd.to_numeric(df[x_col], errors="coerce").dropna()
        y_full = pd.to_numeric(df[y_col], errors="coerce").dropna()

        if len(x_full) >= 5 and len(y_full) >= 5:
            # Full dataset correlation
            full_corr = np.corrcoef(x_full.values[:len(y_full)],
                                     y_full.values[:len(x_full)])[0, 1]

            # Check if there's a "hand-picked" or selection column
            selection_col = None
            for col in df.columns:
                if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
                    unique_vals = df[col].str.lower().unique()
                    if any("yes" in str(v) for v in unique_vals):
                        selection_col = col
                        break

            if selection_col:
                # Use the selection column to identify shown subset
                shown_mask = df[selection_col].str.lower().str.contains("yes", na=False)
                x_shown = pd.to_numeric(df.loc[shown_mask, x_col], errors="coerce").dropna()
                y_shown = pd.to_numeric(df.loc[shown_mask, y_col], errors="coerce").dropna()

                if len(x_shown) >= 3 and len(y_shown) >= 3:
                    shown_corr = np.corrcoef(x_shown.values[:len(y_shown)],
                                              y_shown.values[:len(x_shown)])[0, 1]

                    corr_diff = abs(shown_corr) - abs(full_corr)

                    if corr_diff > 0.15:
                        det.add_finding(
                            "SELECTIVE DATA POINT INCLUSION",
                            f"Only {n_shown} of {n_rows_in_data} data points shown "
                            f"({pct_shown:.0f}%). The shown subset has correlation "
                            f"r={shown_corr:.3f} vs full dataset r={full_corr:.3f}. "
                            f"The selection makes the relationship appear "
                            f"{abs(shown_corr)/max(abs(full_corr), 0.01):.1f}× stronger.",
                            is_cherry_pick=True,
                            impact=min(90, int(60 + corr_diff * 100)),
                            justification="Data points were selectively chosen to create "
                                          "a stronger apparent correlation. Hidden points "
                                          "weaken or break the pattern."
                        )
                        return
                    else:
                        det.add_finding(
                            "SUBSET SHOWN (CONSISTENT)",
                            f"{n_shown} of {n_rows_in_data} points shown. Correlation "
                            f"is similar (shown r={shown_corr:.3f}, full r={full_corr:.3f}).",
                            is_cherry_pick=False,
                            impact=0,
                            justification="Subset doesn't artificially inflate the pattern."
                        )
                        return

            # No selection column — use correlation of full vs estimated subset
            if abs(full_corr) < 0.7 and pct_shown < 40:
                det.add_finding(
                    "FEW DATA POINTS SHOWN",
                    f"Only ~{n_shown} of {n_rows_in_data} data points appear in the graph "
                    f"({pct_shown:.0f}%). Full dataset correlation: r={full_corr:.3f}. "
                    f"Selective point inclusion may create a misleading pattern.",
                    is_cherry_pick=True,
                    impact=55,
                    justification="Showing a small fraction of available data in a scatter "
                                  "plot suggests selective inclusion."
                )


# ══════════════════════════════════════════════════════════════════════════════
# GRAPH DATA EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

def extract_graph_info(image_path: str) -> dict:
    """Extract basic info from graph image using OCR and color analysis."""
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read: {image_path}")

    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # OCR for axis labels
    reader = get_ocr()
    # Upscale small images
    if w < 500:
        scale = 3
        img_ocr = cv2.resize(img, (w*scale, h*scale), interpolation=cv2.INTER_CUBIC)
    else:
        scale = 1
        img_ocr = img

    results = reader.readtext(img_ocr)
    texts = [(text, conf, [c[0]//scale for c in coords], [c[1]//scale for c in coords])
             for (coords, text, conf) in results if conf > 0.2]

    # Extract numeric values from OCR
    numbers = []
    date_labels = []
    for text, conf, xs, ys in texts:
        text_clean = text.strip().replace(",", "").replace(" ", "")
        avg_x = int(np.mean(xs))
        avg_y = int(np.mean(ys))
        try:
            val = float(text_clean)
            numbers.append({"value": val, "x": avg_x, "y": avg_y, "text": text})
        except ValueError:
            # Try parsing as date (YYYY-MM, YYYY-MM-DD, etc.)
            import re
            date_match = re.match(r"(\d{4})-(\d{2})(?:-(\d{2}))?", text_clean)
            if date_match:
                year = int(date_match.group(1))
                month = int(date_match.group(2))
                # Convert to fractional year for numeric comparison
                val = year + (month - 1) / 12.0
                numbers.append({"value": val, "x": avg_x, "y": avg_y, "text": text})
                date_labels.append({"value": val, "x": avg_x, "y": avg_y, "text": text})

    # Detect chart type
    blue_mask = cv2.inRange(hsv, (90, 40, 40), (135, 255, 255))
    red_mask = cv2.inRange(hsv, (0, 40, 40), (15, 255, 255)) | \
               cv2.inRange(hsv, (155, 40, 40), (180, 255, 255))

    blue_count = blue_mask.sum() // 255
    red_count = red_mask.sum() // 255

    # Determine if bar chart or line chart
    # Bar charts have large rectangular colored regions
    blue_ys, blue_xs = np.where(blue_mask > 0)
    is_bar_chart = False
    if len(blue_xs) > 100:
        # Check if blue region is rectangular (bar-like)
        x_range = blue_xs.max() - blue_xs.min()
        y_range = blue_ys.max() - blue_ys.min()
        fill_ratio = len(blue_xs) / (x_range * y_range) if x_range * y_range > 0 else 0
        is_bar_chart = fill_ratio > 0.5  # bars are mostly filled rectangles

    # Find plot boundaries
    row_dark = np.sum(gray < 50, axis=1)
    col_dark = np.sum(gray < 50, axis=0)
    x_axis_y = int(np.argmax(row_dark > w * 0.3)) if row_dark.max() > w * 0.3 else int(h * 0.85)
    y_axis_x = int(np.argmax(col_dark > h * 0.3)) if col_dark.max() > h * 0.3 else int(w * 0.1)

    # Y-axis ticks (numbers on the left side)
    y_ticks = [(n["y"], n["value"]) for n in numbers if n["x"] < y_axis_x + 20]
    y_ticks.sort(key=lambda t: t[0])

    # X-axis ticks (numbers below the plot, well to the right of y-axis)
    x_ticks = [(n["x"], n["value"]) for n in numbers
               if n["y"] > x_axis_y - 30 and n["x"] > y_axis_x + 30]
    x_ticks.sort(key=lambda t: t[0])

    # Filter out x-ticks that are clearly y-axis values leaking in
    # (if a tick value matches a y-tick value, it's probably misplaced)
    if x_ticks and y_ticks:
        y_vals = set(t[1] for t in y_ticks)
        x_ticks = [(px, val) for px, val in x_ticks if val not in y_vals]

    # Determine y-axis range from ticks
    if len(y_ticks) >= 2:
        y_min = min(t[1] for t in y_ticks)
        y_max = max(t[1] for t in y_ticks)
    else:
        y_min, y_max = 0, 1

    # Determine x-axis range from ticks
    if len(x_ticks) >= 2:
        x_min = min(t[1] for t in x_ticks)
        x_max = max(t[1] for t in x_ticks)
    else:
        x_min, x_max = 0, 1

    return {
        "width": w, "height": h,
        "is_bar_chart": is_bar_chart,
        "y_range": (y_min, y_max),
        "x_range": (x_min, x_max),
        "y_ticks": y_ticks,
        "x_ticks": x_ticks,
        "blue_pixels": blue_count,
        "red_pixels": red_count,
        "x_axis_y": x_axis_y,
        "y_axis_x": y_axis_x,
        "all_text": texts,
        "numbers": numbers,
        "_image_path": image_path,
    }

# ══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def detect_cherry_picking(graph_path: str, dataset_path: str, output_dir: str = "output"):
    """Main detection pipeline."""
    os.makedirs(output_dir, exist_ok=True)
    det = CherryPickDetector()

    print("\n" + "="*60)
    print("  CHERRY-PICK DETECTOR v2 (Context-Aware)")
    print("="*60 + "\n")

    # 1. Load dataset
    print(f"[1/4] Loading dataset: {dataset_path}")
    df = load_dataset(dataset_path)
    print(f"      {df.shape[0]} rows × {df.shape[1]} columns")
    numeric_cols = list(df.select_dtypes(include=[np.number]).columns)
    print(f"      Numeric columns: {numeric_cols}")

    # 2. Extract graph info
    print(f"\n[2/4] Analysing graph: {graph_path}")
    ginfo = extract_graph_info(graph_path)
    print(f"      Size: {ginfo['width']}×{ginfo['height']} px")
    print(f"      Type: {'Bar chart' if ginfo['is_bar_chart'] else 'Line/scatter chart'}")
    print(f"      Y-axis range: {ginfo['y_range']}")
    print(f"      X-axis range: {ginfo['x_range']}")
    print(f"      Y ticks: {ginfo['y_ticks']}")
    print(f"      X ticks: {ginfo['x_ticks']}")

    # 3. Run checks
    print(f"\n[3/4] Running context-aware checks…")

    # Check A: Range selection (for time-series / line charts)
    if not ginfo["is_bar_chart"]:
        if len(ginfo["x_ticks"]) >= 2:
            x_min, x_max = ginfo["x_range"]
            # Find the x-column in dataset
            for col in df.columns:
                try:
                    vals = pd.to_numeric(df[col], errors="coerce").dropna()
                    if len(vals) > 0 and vals.max() > x_max * 1.2:
                        check_range_selection(det, df, col, x_min, x_max)
                        break
                except:
                    pass
            else:
                # Try date columns — convert YYYY-MM to fractional year
                import re
                for col in df.columns:
                    sample = str(df[col].iloc[0]) if len(df) > 0 else ""
                    if re.match(r"\d{4}-\d{2}", sample):
                        # Date column — convert to fractional year
                        def to_frac_year(s):
                            m = re.match(r"(\d{4})-(\d{2})", str(s))
                            if m:
                                return int(m.group(1)) + (int(m.group(2)) - 1) / 12.0
                            return np.nan
                        df["_frac_year"] = df[col].apply(to_frac_year)
                        full_min = df["_frac_year"].min()
                        full_max = df["_frac_year"].max()
                        if full_max > x_max * 1.001:  # dataset extends beyond shown
                            check_range_selection(det, df, "_frac_year", x_min, x_max)
                        df.drop("_frac_year", axis=1, inplace=True)
                        break
        else:
            # No numeric x-ticks found — try index-based detection
            # If dataset has many more rows than the graph has data points,
            # the graph might be showing a subset
            # Use the graph's pixel width to estimate how many points are shown
            plot_width = ginfo["width"] - ginfo["y_axis_x"]
            # A typical line chart has ~1 point per 2-5 pixels
            estimated_points = plot_width // 3
            if len(df) > estimated_points * 2 and len(df) > 50:
                # Dataset is much larger than what could fit in the graph
                # Try to find which subset by matching y-values
                y_min_shown, y_max_shown = ginfo["y_range"]
                for col in numeric_cols:
                    col_data = pd.to_numeric(df[col], errors="coerce").dropna()
                    if len(col_data) < 10:
                        continue
                    # Check if only a portion of the data fits the shown y-range
                    in_range = ((col_data >= y_min_shown * 0.9) &
                                (col_data <= y_max_shown * 1.1))
                    pct_in_range = in_range.sum() / len(col_data) * 100
                    if 20 < pct_in_range < 70:
                        # Only a subset matches — check if it's contiguous
                        # (suggesting a time window was selected)
                        idx_col = None
                        for xc in df.columns:
                            if xc != col:
                                try:
                                    xv = pd.to_numeric(df[xc], errors="coerce").dropna()
                                    if len(xv) == len(df) and xv.is_monotonic_increasing:
                                        idx_col = xc
                                        break
                                except:
                                    pass
                        if idx_col:
                            matching_rows = df[in_range]
                            if len(matching_rows) > 5:
                                x_vals = pd.to_numeric(df[idx_col], errors="coerce")
                                s_min = float(x_vals[in_range].min())
                                s_max = float(x_vals[in_range].max())
                                check_range_selection(det, df, idx_col, s_min, s_max)
                                break

    # Check B: Y-axis manipulation
    if len(ginfo["y_ticks"]) >= 2:
        y_min_shown, y_max_shown = ginfo["y_range"]
        # Find matching data range
        for col in numeric_cols:
            data_min = float(df[col].min())
            data_max = float(df[col].max())
            # Check if this column's range overlaps with shown y range
            if data_min <= y_max_shown and data_max >= y_min_shown:
                check_yaxis_manipulation(det, y_min_shown, y_max_shown, data_min, data_max)
                break

    # Check C: Hidden columns
    # Try to identify which column(s) the graph is showing
    shown_cols = []
    for col in numeric_cols:
        col_range = float(df[col].max()) - float(df[col].min())
        y_range = ginfo["y_range"][1] - ginfo["y_range"][0]
        if y_range > 0 and 0.1 < col_range / y_range < 10:
            shown_cols.append(col)

    if shown_cols and len(numeric_cols) > len(shown_cols):
        check_hidden_columns(det, df, shown_cols[:2], numeric_cols)

    # Check D: Sample size (if applicable)
    if len(df) < 30:
        n_per_group = {}
        for col in numeric_cols:
            n_per_group[col] = int(df[col].notna().sum())
        check_sample_size(det, n_per_group)

    # Check E: Statistical selectivity (look for p-values in data)
    p_values = {}
    for col in df.columns:
        col_str = str(col).lower()
        if "p" in col_str or "sig" in col_str:
            vals = pd.to_numeric(df[col], errors="coerce").dropna()
            for i, v in enumerate(vals):
                if 0 < v < 1:
                    p_values[f"{col}_{i}"] = float(v)
    if p_values:
        check_statistical_selectivity(det, p_values)

    # Check F: Selective data point inclusion (Ancel Keys type)
    check_selective_data_points(det, df, ginfo, ginfo.get("all_text", []))

    # 4. Get verdict
    print(f"\n[4/4] Computing verdict…")
    verdict = det.get_verdict()

    print(f"\n      Score: {verdict['score']}/100")
    print(f"      Severity: {verdict['severity']}")
    print(f"      Cherry-pick findings: {len(verdict['cherry_findings'])}")
    print(f"      Legitimate aspects: {len(verdict['legitimate_aspects'])}")
    print(f"      Mitigating factors: {len(verdict['mitigating_factors'])}")

    # Generate outputs
    _generate_outputs(graph_path, dataset_path, df, ginfo, verdict, output_dir)

    return verdict


def _generate_outputs(graph_path, dataset_path, df, ginfo, verdict, output_dir):
    """Generate report and visualisation."""

    # Comparison plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: original graph
    img_rgb = cv2.cvtColor(cv2.imread(graph_path), cv2.COLOR_BGR2RGB)
    axes[0].imshow(img_rgb)
    axes[0].set_title("Analysed Graph", fontsize=11)
    axes[0].axis("off")

    # Right: full dataset overview
    ax = axes[1]
    numeric_cols = list(df.select_dtypes(include=[np.number]).columns)
    colors = plt.cm.tab10.colors
    for i, col in enumerate(numeric_cols[:5]):
        try:
            ax.plot(df.index, pd.to_numeric(df[col], errors="coerce"),
                    color=colors[i % len(colors)], linewidth=0.8, alpha=0.7, label=col)
        except:
            pass
    ax.set_title("Full Dataset Overview", fontsize=11)
    ax.legend(fontsize=7, loc="best")
    ax.grid(True, alpha=0.2)

    sev_colors = {"None/Minimal": "green", "Low": "olive",
                  "Medium": "orange", "High": "red", "Extreme": "darkred"}
    fig.text(0.5, 0.01,
             f"Cherry-Pick Score: {verdict['score']}/100 — Severity: {verdict['severity']}",
             ha="center", fontsize=12, fontweight="bold",
             color=sev_colors.get(verdict["severity"], "black"))

    plt.tight_layout(rect=[0, 0.04, 1, 1])
    plt.savefig(os.path.join(output_dir, "analysis.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Report
    lines = [
        "# Cherry-Pick Detection Report (v2 — Context-Aware)",
        "",
        f"**Graph:** `{graph_path}`",
        f"**Dataset:** `{dataset_path}`",
        "",
        "---",
        "",
        f"## Verdict: {verdict['severity']} (Score: {verdict['score']}/100)",
        "",
        "| Score Range | Meaning |",
        "|-------------|---------|",
        "| 0-20 | Legitimate focused presentation |",
        "| 21-40 | Minor concerns, not misleading |",
        "| 41-60 | Moderate — some misleading framing |",
        "| 61-80 | High — hidden data contradicts shown narrative |",
        "| 81-100 | Extreme — actively deceptive |",
        "",
        "---",
        "",
    ]

    if verdict["cherry_findings"]:
        lines.append("## Cherry-Pick Indicators")
        lines.append("")
        for f in verdict["cherry_findings"]:
            lines.append(f"### ⚠ {f['type']} (impact: {f['impact_score']}/100)")
            lines.append(f"")
            lines.append(f"{f['detail']}")
            lines.append(f"")
            lines.append(f"*Why this matters:* {f['justification']}")
            lines.append("")
    else:
        lines.append("## No Cherry-Picking Detected")
        lines.append("")
        lines.append("The analysis found no evidence that hidden data contradicts")
        lines.append("the graph's presentation.")
        lines.append("")

    if verdict["legitimate_aspects"]:
        lines.append("## Legitimate Aspects")
        lines.append("")
        for f in verdict["legitimate_aspects"]:
            lines.append(f"### ✓ {f['type']}")
            lines.append(f"")
            lines.append(f"{f['detail']}")
            lines.append(f"")
            lines.append(f"*Why this is fine:* {f['justification']}")
            lines.append("")

    if verdict["mitigating_factors"]:
        lines.append("## Mitigating Factors")
        lines.append("")
        for m in verdict["mitigating_factors"]:
            lines.append(f"- {m}")
        lines.append("")

    report_path = os.path.join(output_dir, "cherry_pick_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # Stats JSON
    stats = {
        "score": verdict["score"],
        "severity": verdict["severity"],
        "cherry_findings": len(verdict["cherry_findings"]),
        "legitimate_aspects": len(verdict["legitimate_aspects"]),
        "mitigating_factors": verdict["mitigating_factors"],
    }
    with open(os.path.join(output_dir, "stats.json"), "w") as f:
        json.dump(stats, f, indent=2)

    print(f"\n  [OK] analysis.png")
    print(f"  [OK] cherry_pick_report.md")
    print(f"  [OK] stats.json")
    print(f"  Saved to: {output_dir}/")


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Cherry-Pick Detector v2 — context-aware, no false positives.")
    parser.add_argument("graph", help="Graph image (PNG/JPG)")
    parser.add_argument("dataset", help="Dataset (CSV/Excel/JSON)")
    parser.add_argument("--output", default="output", help="Output directory")
    args = parser.parse_args()
    detect_cherry_picking(args.graph, args.dataset, args.output)
