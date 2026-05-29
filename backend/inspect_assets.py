"""Extract visual assets from a PDF and save them to disk for inspection."""
import os
import sys
import base64

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app.extractor import extract_visual_assets

TEST_PDF = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "test_docs",
    "The cellular coding of temperature in the_compressed.pdf"
)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extracted_assets")
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"Reading: {TEST_PDF}")
with open(TEST_PDF, "rb") as f:
    pdf_bytes = f.read()

print("Extracting visual assets...")
assets = extract_visual_assets(pdf_bytes)
print(f"Found {len(assets)} assets\n")

for i, asset in enumerate(assets):
    page = asset.get("page_number", "?")
    atype = asset.get("type", "unknown")
    w = asset.get("width", 0)
    h = asset.get("height", 0)
    img_data = asset.get("image_data", "")

    filename = f"page{page}_{i+1:02d}_{atype}_{w}x{h}.png"
    filepath = os.path.join(OUTPUT_DIR, filename)

    img_bytes = base64.b64decode(img_data)
    with open(filepath, "wb") as f:
        f.write(img_bytes)

    print(f"  [{i+1:2d}] Page {page} | {atype:6s} | {w}x{h} | {filename}")

print(f"\nSaved {len(assets)} images to: {OUTPUT_DIR}")
