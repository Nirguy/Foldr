"""Debug the classification of extracted panels."""
import os, sys, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.extractor import _detect_number_labels, _detect_axis_lines, _has_substantial_plot_area

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extracted_assets")

files = sorted(os.listdir(ASSETS_DIR))[:10]  # Check first 10
for fname in files:
    path = os.path.join(ASSETS_DIR, fname)
    img = cv2.imread(path)
    if img is None:
        continue
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    has_numbers = _detect_number_labels(gray, h, w)
    has_axes = _detect_axis_lines(gray, h, w)
    has_plot = _has_substantial_plot_area(gray, h, w)

    # Also check unique grays and content ratio
    WHITE_THRESH = 235
    content_ratio = np.sum(gray < WHITE_THRESH) / (h * w)
    interior = gray[int(h*0.1):int(h*0.9), int(w*0.1):int(w*0.9)]
    unique_grays = len(np.unique(interior)) if interior.size > 0 else 0
    white_ratio = np.sum(gray >= WHITE_THRESH) / (h * w)

    print(f"{fname[:45]:45s} | nums={has_numbers} axes={has_axes} plot={has_plot} | content={content_ratio:.2f} uniq={unique_grays} white={white_ratio:.2f}")
