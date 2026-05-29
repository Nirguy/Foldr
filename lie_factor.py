"""
Lie Factor Analyzer
Receives a dataset and a list of graph images.
Returns how many graphs passed/failed the lie factor test.

Usage as import:
    from lie_factor import analyze_graphs
    result = analyze_graphs("data.csv", ["graph1.png", "graph2.png"])

Usage from CLI:
    python lie_factor.py data.csv graph1.png graph2.png graph3.png
"""

import sys
import json
import numpy as np
import pandas as pd
from PIL import Image
from pathlib import Path
from dataclasses import dataclass


# ============================================================
# CORE: Lie Factor Calculation
# ============================================================

@dataclass
class LieFactorResult:
    lie_factor: float
    passed: bool


def _size_of_effect(v1: float, v2: float) -> float:
    if v1 == 0:
        raise ValueError("Division by zero")
    return abs(v2 - v1) / abs(v1)


def _compute_lie_factor_multi(data_values: list, graphic_values: list) -> LieFactorResult:
    """Compute average Lie Factor across consecutive pairs."""
    if len(data_values) != len(graphic_values) or len(data_values) < 2:
        return LieFactorResult(lie_factor=float("inf"), passed=False)

    lie_factors = []
    for i in range(len(data_values) - 1):
        d1, d2 = data_values[i], data_values[i + 1]
        g1, g2 = graphic_values[i], graphic_values[i + 1]
        if d1 == 0 or g1 == 0:
            continue
        try:
            effect_data = _size_of_effect(d1, d2)
            effect_graphic = _size_of_effect(g1, g2)
            if effect_data == 0:
                if effect_graphic == 0:
                    lie_factors.append(1.0)
            else:
                lie_factors.append(effect_graphic / effect_data)
        except (ValueError, ZeroDivisionError):
            continue

    if not lie_factors:
        return LieFactorResult(lie_factor=float("inf"), passed=False)

    avg = float(np.mean(lie_factors))
    return LieFactorResult(lie_factor=avg, passed=(0.5 <= avg <= 1.5))


# ============================================================
# IMAGE ANALYSIS: Detect chart type and measure visual values
# ============================================================

def _get_bg_color(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    edge_pixels = np.concatenate([
        img[0:10, :, :].reshape(-1, 3),
        img[-10:, :, :].reshape(-1, 3),
        img[:, 0:10, :].reshape(-1, 3),
        img[:, -10:, :].reshape(-1, 3),
    ])
    return np.median(edge_pixels, axis=0).astype(float)


def _get_content_mask(img: np.ndarray, bg_color: np.ndarray) -> np.ndarray:
    """Find the dominant colored content (bars or line)."""
    diff = np.max(np.abs(img.astype(float) - bg_color), axis=2)
    content_mask = diff > 40
    gray = np.mean(img, axis=2)
    candidate_mask = content_mask & (gray > 50) & (gray < 230)

    coords = np.where(candidate_mask)
    if len(coords[0]) == 0:
        return content_mask

    n_samples = min(5000, len(coords[0]))
    np.random.seed(42)
    indices = np.random.choice(len(coords[0]), n_samples, replace=False)
    sample_pixels = img[coords[0][indices], coords[1][indices]]

    quantized = (sample_pixels // 30) * 30
    unique_colors, counts = np.unique(quantized, axis=0, return_counts=True)

    best_color = None
    best_count = 0
    for color, count in zip(unique_colors, counts):
        r, g, b = int(color[0]), int(color[1]), int(color[2])
        if r < 60 and g < 60 and b < 60:
            continue
        if abs(r - g) < 30 and abs(g - b) < 30 and r < 180:
            continue
        if count > best_count:
            best_count = count
            best_color = color

    if best_color is None:
        best_color = unique_colors[np.argmax(counts)]

    color_diff = np.sqrt(np.sum((img.astype(float) - best_color.astype(float)) ** 2, axis=2))
    return color_diff < 60


def _detect_chart_type(img: np.ndarray, bg_color: np.ndarray) -> str:
    gray = np.mean(img, axis=2)
    diff = np.max(np.abs(img.astype(float) - bg_color), axis=2)
    colored_mask = (diff > 40) & (gray > 60) & (gray < 220)
    ratio = np.sum(colored_mask) / (img.shape[0] * img.shape[1])
    return "bar" if ratio > 0.04 else "line"


def _measure_bars(img: np.ndarray, mask: np.ndarray) -> list:
    h, w = img.shape[:2]
    row_sum = np.sum(mask, axis=1)

    baseline_y = h - 1
    for y in range(h - 1, h // 4, -1):
        if row_sum[y] > w * 0.03:
            baseline_y = y
            break

    top_y = 0
    for y in range(h // 2):
        if row_sum[y] > w * 0.02:
            top_y = y
            break

    if baseline_y <= top_y:
        return []

    chart_height = baseline_y - top_y
    work_mask = mask[top_y:baseline_y, :]

    col_sums = np.sum(work_mask, axis=0).astype(float)
    kernel_size = max(3, w // 100)
    col_sums_smooth = np.convolve(col_sums, np.ones(kernel_size) / kernel_size, mode="same")

    threshold = np.max(col_sums_smooth) * 0.1
    is_bar_col = col_sums_smooth > threshold

    bars = []
    in_bar = False
    bar_start = 0
    for x in range(len(is_bar_col)):
        if is_bar_col[x] and not in_bar:
            bar_start = x
            in_bar = True
        elif not is_bar_col[x] and in_bar:
            if x - bar_start > w * 0.01:
                bars.append((bar_start, x))
            in_bar = False
    if in_bar and len(is_bar_col) - bar_start > w * 0.01:
        bars.append((bar_start, len(is_bar_col)))

    if not bars:
        return []

    heights = []
    for bs, be in bars:
        margin = int((be - bs) * 0.2)
        cs, ce = bs + margin, be - margin
        if ce <= cs:
            cs, ce = bs, be
        strip = work_mask[:, cs:ce]
        bar_rows = np.where(np.any(strip, axis=1))[0]
        if len(bar_rows) > 0:
            heights.append(float(chart_height - bar_rows[0]))
        else:
            heights.append(0.0)

    return heights


def _measure_line(img: np.ndarray, mask: np.ndarray, num_points: int) -> list:
    h, w = img.shape[:2]

    col_content = np.sum(mask, axis=0)
    line_cols = np.where(col_content > 0)[0]
    if len(line_cols) == 0:
        return [0.0] * num_points

    x_start = line_cols[0]
    x_end = line_cols[-1]
    usable_width = x_end - x_start
    if usable_width <= 0:
        return [0.0] * num_points

    # Find chart bottom (x-axis)
    gray = np.mean(img, axis=2)
    chart_bottom = int(h * 0.85)
    for y in range(h - 1, h // 2, -1):
        if np.sum(gray[y, :] < 80) > w * 0.5:
            chart_bottom = y
            break

    chart_top = int(h * 0.05)
    chart_height = chart_bottom - chart_top
    if chart_height <= 0:
        return [0.0] * num_points

    heights = []
    for i in range(num_points):
        x_pos = x_start + int(i * usable_width / max(num_points - 1, 1))
        window = max(3, usable_width // (num_points * 2))
        x_lo = max(0, x_pos - window)
        x_hi = min(w, x_pos + window)

        strip = mask[chart_top:chart_bottom, x_lo:x_hi]
        row_has_line = np.any(strip, axis=1)
        line_rows = np.where(row_has_line)[0]

        if len(line_rows) > 0:
            line_y = int(np.median(line_rows))
            heights.append(float(max(chart_height - line_y, 1)))
        else:
            heights.append(0.0)

    # Interpolate zeros
    for i in range(len(heights)):
        if heights[i] == 0:
            left = right = None
            for j in range(i - 1, -1, -1):
                if heights[j] > 0:
                    left = (j, heights[j])
                    break
            for j in range(i + 1, len(heights)):
                if heights[j] > 0:
                    right = (j, heights[j])
                    break
            if left and right:
                t = (i - left[0]) / (right[0] - left[0])
                heights[i] = left[1] + t * (right[1] - left[1])
            elif left:
                heights[i] = left[1]
            elif right:
                heights[i] = right[1]

    return heights


# ============================================================
# DATA AGGREGATION
# ============================================================

def _aggregate_data(df, value_col, num_groups, method="sum"):
    data_series = pd.to_numeric(df[value_col], errors="coerce").dropna()
    n = len(data_series)

    if n == num_groups:
        return data_series.tolist()
    if n < num_groups:
        return data_series.tolist()

    date_cols = [c for c in df.columns if "date" in c.lower() or "time" in c.lower()]
    if date_cols:
        try:
            dates = pd.to_datetime(df[date_cols[0]], errors="coerce")
            if dates.notna().sum() > 0:
                temp_df = pd.DataFrame({
                    "date": dates,
                    "value": pd.to_numeric(df[value_col], errors="coerce"),
                }).dropna()
                agg_func = "mean" if method == "mean" else "sum"
                for freq in ["QE", "ME", "YE"]:
                    grouped = temp_df.set_index("date").resample(freq)["value"].agg(agg_func)
                    grouped = grouped[grouped > 0]
                    if len(grouped) == num_groups:
                        return grouped.tolist()
        except Exception:
            pass

    # Fallback: equal chunks
    chunk_size = n // num_groups
    data_list = data_series.tolist()
    aggregated = []
    for i in range(num_groups):
        start = i * chunk_size
        end = start + chunk_size if i < num_groups - 1 else n
        chunk = data_list[start:end]
        aggregated.append(sum(chunk) / len(chunk) if method == "mean" else sum(chunk))
    return aggregated


# ============================================================
# PUBLIC API
# ============================================================

def analyze_single(df, value_col: str, image_path: str) -> dict:
    """Analyze one graph image against the dataset."""
    try:
        pil_image = Image.open(image_path)
    except Exception as e:
        return {"image": image_path, "lie_factor": None, "passed": False, "error": str(e)}

    img = np.array(pil_image.convert("RGB"))
    bg_color = _get_bg_color(img)
    chart_type = _detect_chart_type(img, bg_color)
    mask = _get_content_mask(img, bg_color)

    try:
        if chart_type == "bar":
            pixel_heights = _measure_bars(img, mask)
            if not pixel_heights or max(pixel_heights) == 0:
                return {"image": image_path, "lie_factor": None, "passed": False, "error": "No bars detected"}
            aggregated = _aggregate_data(df, value_col, len(pixel_heights), method="sum")
        else:
            # Determine sample count
            num_points = None
            date_cols = [c for c in df.columns if "date" in c.lower() or "time" in c.lower()]
            if date_cols:
                try:
                    dates = pd.to_datetime(df[date_cols[0]], errors="coerce")
                    data_series = pd.to_numeric(df[value_col], errors="coerce").dropna()
                    temp_df = pd.DataFrame({"date": dates[:len(data_series)], "value": data_series.values}).dropna()
                    monthly = temp_df.set_index("date").resample("ME")["value"].mean()
                    monthly = monthly[monthly > 0]
                    num_points = len(monthly)
                except Exception:
                    pass
            if not num_points or num_points < 2:
                num_points = min(len(pd.to_numeric(df[value_col], errors="coerce").dropna()), 30)

            pixel_heights = _measure_line(img, mask, num_points)
            if not pixel_heights or max(pixel_heights) == 0:
                return {"image": image_path, "lie_factor": None, "passed": False, "error": "No line detected"}
            aggregated = _aggregate_data(df, value_col, num_points, method="mean")

        # Align
        min_len = min(len(aggregated), len(pixel_heights))
        if min_len < 2:
            return {"image": image_path, "lie_factor": None, "passed": False, "error": "Not enough points"}

        result = _compute_lie_factor_multi(aggregated[:min_len], pixel_heights[:min_len])
        return {
            "image": image_path,
            "lie_factor": round(result.lie_factor, 3),
            "passed": result.passed,
            "chart_type": chart_type,
        }

    except Exception as e:
        return {"image": image_path, "lie_factor": None, "passed": False, "error": str(e)}


def analyze_graphs(data_path: str, image_paths: list) -> dict:
    """
    Main API. Analyze multiple graph images against a dataset.

    Returns the average of all positive (> 0) lie factors across all input
    graphs, minus 1. If no reasonable lie factor can be detected from any
    graph, returns -1.

    Args:
        data_path: Path to CSV or Excel file.
        image_paths: List of graph image paths.

    Returns:
        {
            "lie_factor": float,  # average of positive lie factors - 1, or -1 if undetectable
            "total": int,
            "passed": int,
            "failed": int,
            "results": [...]
        }
    """
    path = Path(data_path)
    if path.suffix in (".xlsx", ".xls"):
        df = pd.read_excel(data_path)
    else:
        df = pd.read_csv(data_path)

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if not numeric_cols:
        raise ValueError("No numeric columns found in data file.")

    value_col = numeric_cols[0]
    results = [analyze_single(df, value_col, p) for p in image_paths]

    passed = sum(1 for r in results if r["passed"])

    # Collect all positive, finite lie factors
    positive_lie_factors = [
        r["lie_factor"]
        for r in results
        if r["lie_factor"] is not None
        and r["lie_factor"] > 0
        and np.isfinite(r["lie_factor"])
    ]

    if positive_lie_factors:
        avg_lie_factor = float(np.mean(positive_lie_factors)) - 1
    else:
        # Can't detect a reasonable lie factor from any graph
        avg_lie_factor = -1

    return {
        "lie_factor": round(avg_lie_factor, 3),
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python lie_factor.py <data_file> <image1> [image2] ...")
        sys.exit(1)

    output = analyze_graphs(sys.argv[1], sys.argv[2:])
    print(json.dumps(output, indent=2))
