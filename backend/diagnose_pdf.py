"""Diagnostic script: Analyze how figures are stored in a PDF.

Usage: python diagnose_pdf.py /path/to/paper.pdf
"""
import sys
import fitz


def diagnose(path: str):
    doc = fitz.open(path)
    print(f"PDF: {path}")
    print(f"Pages: {doc.page_count}")
    print()

    for page_index in range(min(doc.page_count, 5)):  # Check first 5 pages
        page = doc[page_index]
        print(f"--- Page {page_index + 1} ---")

        # Images
        images = page.get_images(full=True)
        print(f"  Raster images: {len(images)}")
        for img in images[:3]:
            print(f"    xref={img[0]}, {img[2]}x{img[3]}, cs={img[4]}, bpc={img[5]}")

        # Drawings
        drawings = page.get_drawings()
        print(f"  Vector drawings: {len(drawings)}")
        if drawings:
            # Summarize drawing types
            large_drawings = [d for d in drawings if d["rect"][2] - d["rect"][0] > 50 and d["rect"][3] - d["rect"][1] > 50]
            print(f"    Large drawings (>50pt): {len(large_drawings)}")
            if large_drawings[:3]:
                for d in large_drawings[:3]:
                    r = d["rect"]
                    print(f"      rect=({r[0]:.0f},{r[1]:.0f},{r[2]:.0f},{r[3]:.0f}), items={len(d.get('items', []))}")

        # XObjects (Form objects = self-contained figure groups)
        xobjects = page.get_xobjects()
        print(f"  XObjects (Form): {len(xobjects)}")
        for xobj in xobjects[:5]:
            print(f"    {xobj}")

        # Text blocks with "Fig" to show caption locations
        text_dict = page.get_text("dict")
        fig_blocks = []
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text += span.get("text", "")
            if "Fig" in text or "figure" in text.lower():
                bbox = block.get("bbox")
                fig_blocks.append((text[:60], bbox))

        if fig_blocks:
            print(f"  Figure captions found: {len(fig_blocks)}")
            for text, bbox in fig_blocks[:3]:
                print(f"    '{text}...' at y={bbox[1]:.0f}-{bbox[3]:.0f}")

        print()

    doc.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python diagnose_pdf.py /path/to/paper.pdf")
        sys.exit(1)
    diagnose(sys.argv[1])
