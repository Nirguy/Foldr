"""
crop_charts.py

Splits each image in a folder into individual chart crops and saves them
to an output folder.

Algorithm:
  1. Build a dark-pixel projection profile (row-wise and column-wise)
  2. Find near-empty bands (gutters) between charts using valley detection
  3. Filter out cells that are too small or have too little content
  4. Save each valid cell as a separate PNG

Usage:
    python crop_charts.py                          # pictures/ -> cropped_charts/
    python crop_charts.py --input pictures/ --output cropped_charts/
    python crop_charts.py --debug                  # also save annotated images
"""

import argparse
from pathlib import Path

import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}


# ---------------------------------------------------------------------------
# Projection-profile valley detection
# ---------------------------------------------------------------------------

def dark_profile(gray: np.ndarray, axis: int, threshold: int = 200) -> np.ndarray:
    """Count dark pixels (< threshold) along the given axis."""
    return (gray < threshold).sum(axis=axis).astype(float)


def smooth(arr: np.ndarray, k: int = 5) -> np.ndarray:
    return np.convolve(arr, np.ones(k) / k, mode='same')


def find_valleys(profile: np.ndarray, total: int,
                 min_band_px: int = 12,
                 min_cell_frac: float = 0.10) -> list:
    """
    Find cut positions (centers of near-zero bands) in a dark-pixel profile.

    A band is 'near-zero' if its value is <= 1% of the profile maximum.
    """
    max_val = profile.max()
    if max_val == 0:
        return []

    empty_thresh = max(1.5, max_val * 0.01)
    is_empty = profile <= empty_thresh

    bands = []
    in_band = False
    start = 0
    for i in range(total):
        if is_empty[i] and not in_band:
            in_band = True
            start = i
        elif not is_empty[i] and in_band:
            in_band = False
            width = i - start
            center = (start + i) // 2
            if width >= min_band_px:
                bands.append((center, width))
    if in_band:
        width = total - start
        center = (start + total) // 2
        if width >= min_band_px:
            bands.append((center, width))

    # Remove cuts too close to edges or producing tiny cells
    min_cell = int(total * min_cell_frac)
    cuts = []
    prev = 0
    for center, _ in sorted(bands):
        if center - prev >= min_cell and total - center >= min_cell:
            cuts.append(center)
            prev = center

    return cuts


# ---------------------------------------------------------------------------
# Cell quality filter
# ---------------------------------------------------------------------------

def is_valid_cell(gray_crop: np.ndarray,
                  full_h: int, full_w: int,
                  min_dark_ratio: float = 0.02,
                  min_size_frac: float = 0.08) -> bool:
    """
    Return True if this crop looks like a real chart (not a margin/header/footer).
    """
    ch, cw = gray_crop.shape
    # Must be large enough relative to the full image
    if ch < full_h * min_size_frac or cw < full_w * min_size_frac:
        return False
    # Must have enough dark content
    dark_ratio = (gray_crop < 200).sum() / (ch * cw)
    if dark_ratio < min_dark_ratio:
        return False
    return True


# ---------------------------------------------------------------------------
# Main split function
# ---------------------------------------------------------------------------

def split_image(image: Image.Image) -> list:
    """
    Split a PIL image into individual chart crops.

    Returns list of (PIL.Image crop, (x1, y1, x2, y2)) tuples.
    """
    rgb = image.convert("RGB")
    img_np = np.array(rgb)
    h, w = img_np.shape[:2]
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

    row_profile = smooth(dark_profile(gray, axis=1))   # dark pixels per row
    col_profile = smooth(dark_profile(gray, axis=0))   # dark pixels per col

    h_cuts = find_valleys(row_profile, h, min_band_px=12, min_cell_frac=0.10)
    v_cuts = find_valleys(col_profile, w, min_band_px=12, min_cell_frac=0.10)

    h_edges = [0] + h_cuts + [h]
    v_edges = [0] + v_cuts + [w]

    crops = []
    for r in range(len(h_edges) - 1):
        for c in range(len(v_edges) - 1):
            y1, y2 = h_edges[r], h_edges[r + 1]
            x1, x2 = v_edges[c], v_edges[c + 1]
            gray_crop = gray[y1:y2, x1:x2]
            if is_valid_cell(gray_crop, h, w):
                crop_img = rgb.crop((x1, y1, x2, y2))
                crops.append((crop_img, (x1, y1, x2, y2)))

    # Fallback: nothing found → return whole image
    if not crops:
        crops = [(rgb, (0, 0, w, h))]

    return crops


# ---------------------------------------------------------------------------
# Debug annotation
# ---------------------------------------------------------------------------

def annotate_image(image: Image.Image, crops: list) -> Image.Image:
    colors = ["red", "blue", "green", "orange", "purple",
              "cyan", "magenta", "yellow", "lime", "pink"]
    out = image.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    for i, (_, (x1, y1, x2, y2)) in enumerate(crops):
        color = colors[i % len(colors)]
        draw.rectangle([x1, y1, x2, y2], outline=color, width=5)
        draw.rectangle([x1, y1, x1 + 30, y1 + 24], fill=color)
        draw.text((x1 + 4, y1 + 4), str(i + 1), fill="white")
    return out


# ---------------------------------------------------------------------------
# Main routine
# ---------------------------------------------------------------------------

def crop_all(input_dir: str, output_dir: str, debug: bool = False) -> None:
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if debug:
        debug_path = output_path / "debug"
        debug_path.mkdir(exist_ok=True)

    image_files = sorted(
        f for f in input_path.iterdir()
        if f.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if not image_files:
        print(f"No images found in '{input_dir}'")
        return

    total_saved = 0

    for img_file in image_files:
        print(f"\nProcessing: {img_file.name}")
        image = Image.open(img_file)
        w, h = image.size

        crops = split_image(image)
        print(f"  -> {len(crops)} chart(s) detected  (image: {w}x{h})")

        stem = img_file.stem

        for i, (crop_img, box) in enumerate(crops, 1):
            out_name = f"{stem}_chart{i:02d}.png"
            out_path = output_path / out_name
            crop_img.save(out_path)
            cw, ch = crop_img.size
            x1, y1, x2, y2 = box
            print(f"     [{i}] {out_name}  ({cw}x{ch}px)  box=({x1},{y1})-({x2},{y2})")
            total_saved += 1

        if debug:
            annotated = annotate_image(image, crops)
            scale = min(1.0, 1000 / max(w, h))
            annotated_small = annotated.resize(
                (int(w * scale), int(h * scale)), Image.LANCZOS
            )
            debug_name = f"{stem}_annotated.png"
            annotated_small.save(debug_path / debug_name)
            print(f"     Debug saved: cropped_charts/debug/{debug_name}")

    print(f"\nDone. {total_saved} chart image(s) saved to '{output_dir}/'")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Crop multi-chart images into individual chart files."
    )
    parser.add_argument("--input", "-i", default="pictures",
                        help="Folder with source images (default: pictures/)")
    parser.add_argument("--output", "-o", default="cropped_charts",
                        help="Output folder (default: cropped_charts/)")
    parser.add_argument("--debug", action="store_true",
                        help="Save annotated debug images showing detected boxes")
    args = parser.parse_args()
    crop_all(args.input, args.output, debug=args.debug)


if __name__ == "__main__":
    main()
