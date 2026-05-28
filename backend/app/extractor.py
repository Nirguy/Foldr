# PDF Extractor - extraction logic for metadata, content, methods, and visual assets

import base64
import re
from datetime import datetime

import cv2
import fitz  # PyMuPDF
import numpy as np


def extract_metadata(pdf_bytes: bytes) -> dict | None:
    """Extract metadata from a PDF file.

    Uses PyMuPDF to read document metadata (title, author, etc.) and
    first-page text heuristics for institutions and journal name.

    Returns a dict with keys: title, authors, institutions, journal, date.
    Returns None if extraction fails entirely.
    Individual fields that fail are set to None while others are populated.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return None

    try:
        meta = doc.metadata or {}
        first_page_text = ""
        try:
            if doc.page_count > 0:
                first_page_text = doc[0].get_text() or ""
        except Exception:
            first_page_text = ""

        # --- Title ---
        title = _extract_title(meta, first_page_text)

        # --- Authors ---
        authors = _extract_authors(meta, first_page_text)

        # --- Institutions ---
        institutions = _extract_institutions(first_page_text)

        # --- Journal ---
        journal = _extract_journal(meta, first_page_text)

        # --- Date ---
        date = _extract_date(meta)

        # Truncate to schema limits
        if title and len(title) > 500:
            title = title[:500]
        if authors and len(authors) > 50:
            authors = authors[:50]
        if institutions and len(institutions) > 50:
            institutions = institutions[:50]
        if journal and len(journal) > 300:
            journal = journal[:300]

        result = {
            "title": title,
            "authors": authors,
            "institutions": institutions,
            "journal": journal,
            "date": date,
        }

        doc.close()
        return result

    except Exception:
        try:
            doc.close()
        except Exception:
            pass
        return None


def _extract_title(meta: dict, first_page_text: str) -> str | None:
    """Extract title from PDF metadata or first-page text."""
    try:
        # Try metadata first
        title = meta.get("title", "").strip()
        if title:
            return title

        # Heuristic: first non-empty line of the first page is often the title
        if first_page_text:
            lines = [line.strip() for line in first_page_text.split("\n") if line.strip()]
            if lines:
                # Take the first substantial line (skip very short lines like page numbers)
                for line in lines:
                    if len(line) > 5:
                        return line
                # Fallback to first line if all are short
                return lines[0]
        return None
    except Exception:
        return None


def _extract_authors(meta: dict, first_page_text: str) -> list[str] | None:
    """Extract author names from PDF metadata or first-page text."""
    try:
        author_str = meta.get("author", "").strip()
        if author_str:
            # Authors may be separated by commas, semicolons, or "and"
            authors = _parse_author_string(author_str)
            if authors:
                return authors

        # Heuristic: look for author-like patterns in first page text
        if first_page_text:
            authors = _extract_authors_from_text(first_page_text)
            if authors:
                return authors

        return None
    except Exception:
        return None


def _parse_author_string(author_str: str) -> list[str]:
    """Parse an author string into a list of individual names."""
    # Replace "and" with comma for uniform splitting
    normalized = re.sub(r'\band\b', ',', author_str, flags=re.IGNORECASE)
    # Split on commas or semicolons
    parts = re.split(r'[;,]', normalized)
    authors = [part.strip() for part in parts if part.strip()]
    return authors


def _extract_authors_from_text(text: str) -> list[str] | None:
    """Try to extract authors from first-page text using heuristics."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # Look for lines that appear after the title and before institutional affiliations
    # Authors are typically on lines 2-5, containing names (capitalized words)
    # separated by commas or listed one per line
    candidate_lines = []
    for i, line in enumerate(lines[1:6], start=1):  # Skip first line (likely title)
        # Skip lines that look like affiliations (contain "University", "Institute", etc.)
        if _looks_like_institution(line):
            break
        # Skip lines that look like abstracts or section headers
        if line.lower().startswith(("abstract", "introduction", "keywords")):
            break
        # Author lines typically have capitalized words and commas
        if _looks_like_author_line(line):
            candidate_lines.append(line)

    if candidate_lines:
        # Join all candidate lines and parse as one author string
        combined = ", ".join(candidate_lines)
        authors = _parse_author_string(combined)
        if authors:
            return authors

    return None


def _looks_like_author_line(line: str) -> bool:
    """Check if a line looks like it contains author names."""
    # Author lines typically have multiple capitalized words
    # and don't contain typical non-author indicators
    non_author_indicators = [
        "university", "institute", "department", "school",
        "abstract", "introduction", "journal", "vol.", "doi:",
        "received", "accepted", "published", "@",
    ]
    lower = line.lower()
    for indicator in non_author_indicators:
        if indicator in lower:
            return False

    # Should have at least one capitalized word that looks like a name
    words = line.split()
    capitalized = sum(1 for w in words if w[0:1].isupper()) if words else 0
    return capitalized >= 2 and len(line) < 200


def _extract_institutions(first_page_text: str) -> list[str] | None:
    """Extract institution names from first-page text using heuristics."""
    try:
        if not first_page_text:
            return None

        lines = [line.strip() for line in first_page_text.split("\n") if line.strip()]
        institutions = []

        for line in lines[:20]:  # Only check first 20 lines
            if _looks_like_institution(line):
                # Clean up the line (remove leading numbers, superscripts, etc.)
                cleaned = re.sub(r'^[\d\s*†‡§¶]+', '', line).strip()
                if cleaned and cleaned not in institutions:
                    institutions.append(cleaned)

        return institutions if institutions else None
    except Exception:
        return None


def _looks_like_institution(line: str) -> bool:
    """Check if a line looks like an institutional affiliation."""
    institution_keywords = [
        "university", "institute", "college", "school of",
        "department", "faculty", "laboratory", "lab",
        "hospital", "medical center", "centre",
        "research center", "research centre",
        "academy", "polytechnic",
    ]
    lower = line.lower()
    return any(keyword in lower for keyword in institution_keywords)


def _extract_journal(meta: dict, first_page_text: str) -> str | None:
    """Extract journal name from metadata or first-page text."""
    try:
        # Check metadata fields that might contain journal info
        # PyMuPDF metadata may have "subject" or "keywords" with journal info
        for key in ("subject", "keywords"):
            value = meta.get(key, "").strip()
            if value and _looks_like_journal(value):
                return value

        # Heuristic: look for journal-like patterns in first page text
        if first_page_text:
            lines = [line.strip() for line in first_page_text.split("\n") if line.strip()]
            for line in lines[:15]:  # Check first 15 lines
                # Look for patterns like "Journal of ...", "Proceedings of ..."
                journal_match = re.match(
                    r'((?:Journal|Proceedings|Transactions|Annals|Bulletin|Review|Reviews)'
                    r'\s+(?:of|on)\s+.+?)(?:\s*[,\d]|$)',
                    line,
                    re.IGNORECASE,
                )
                if journal_match:
                    return journal_match.group(1).strip()

                # Look for lines with volume/issue indicators
                if re.search(r'\bVol\.?\s*\d+', line, re.IGNORECASE):
                    # The journal name is likely the text before "Vol."
                    parts = re.split(r'\bVol\.?\s*\d+', line, flags=re.IGNORECASE)
                    if parts[0].strip():
                        return parts[0].strip().rstrip(',').strip()

        return None
    except Exception:
        return None


def _looks_like_journal(text: str) -> bool:
    """Check if text looks like a journal name."""
    journal_indicators = [
        "journal", "proceedings", "transactions", "annals",
        "bulletin", "review", "letters", "communications",
    ]
    lower = text.lower()
    return any(indicator in lower for indicator in journal_indicators)


def _extract_date(meta: dict) -> str | None:
    """Extract and format publication date as ISO 8601 YYYY-MM-DD or None."""
    try:
        # PyMuPDF stores dates in format like "D:20230115120000+00'00'"
        date_str = meta.get("creationDate", "") or meta.get("modDate", "")
        if not date_str:
            return None

        # Parse PyMuPDF date format: D:YYYYMMDDHHmmSS...
        match = re.match(r"D:(\d{4})(\d{2})(\d{2})", date_str)
        if match:
            year, month, day = match.groups()
            # Validate the date
            try:
                dt = datetime(int(year), int(month), int(day))
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                # Invalid date components, try just the year
                return f"{year}-01-01"

        # Try other common date formats
        # Some PDFs have plain date strings
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y"):
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        # Try to extract just a year
        year_match = re.search(r'(\d{4})', date_str)
        if year_match:
            year = int(year_match.group(1))
            if 1900 <= year <= 2100:
                return f"{year}-01-01"

        return None
    except Exception:
        return None


def extract_content(pdf_bytes: bytes) -> tuple[str | None, list[int]]:
    """Extract full text content from a PDF, preserving page order and paragraph boundaries.

    Iterates through all pages in order, extracting text blocks from each page.
    Text blocks within a page are joined with double newlines to preserve paragraph
    boundaries. Pages where no text can be extracted are tracked in skipped_pages.

    Args:
        pdf_bytes: Raw PDF file bytes.

    Returns:
        A tuple of (content, skipped_pages) where:
        - content is the concatenated text string, or None if all pages failed
        - skipped_pages is a list of 1-indexed page numbers where extraction failed
    """
    skipped_pages: list[int] = []
    page_texts: list[str] = []

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        # If the PDF can't be opened at all, all pages are considered failed
        return (None, [])

    try:
        for page_index in range(len(doc)):
            page_number = page_index + 1  # 1-indexed
            try:
                page = doc[page_index]
                # Extract text blocks from the page
                blocks = page.get_text("blocks")
                # Each block is a tuple: (x0, y0, x1, y1, text, block_no, block_type)
                # block_type 0 = text, 1 = image
                text_blocks = [
                    block[4].strip()
                    for block in blocks
                    if block[6] == 0 and block[4].strip()
                ]

                if not text_blocks:
                    skipped_pages.append(page_number)
                else:
                    page_text = "\n\n".join(text_blocks)
                    page_texts.append(page_text)
            except Exception:
                skipped_pages.append(page_number)
    finally:
        doc.close()

    if not page_texts:
        return (None, skipped_pages)

    concatenated_text = "\n\n".join(page_texts)
    return (concatenated_text, skipped_pages)


def extract_research_methods(full_text: str) -> str | None:
    """Extract the research methods section from the full text of a paper.

    Searches for section headings matching predefined methods-related headings
    (case-insensitive). Extracts text from the first matched heading up to the
    next section heading of equal or higher level.

    Args:
        full_text: The full extracted text content of the paper.

    Returns:
        The methods section text, or None if no matching heading is found.
    """
    if not full_text:
        return None

    # Define the target headings to search for (order matters for matching priority)
    methods_headings = [
        "Materials and Methods",
        "Research Methods",
        "Experimental Design",
        "Research Design",
        "Methodology",
        "Methods",
    ]

    # Build a regex pattern that matches any of the target headings as section headings.
    # A section heading is typically on its own line, possibly preceded by a number/letter
    # and followed by optional whitespace/punctuation.
    # We look for lines that start with optional numbering then the heading text.
    heading_alternatives = "|".join(re.escape(h) for h in methods_headings)

    # Pattern to find a methods heading: start of line, optional numbering (e.g., "3.", "III.", "3.1"),
    # then the heading text, case-insensitive
    methods_heading_pattern = re.compile(
        r'^(?:\d+(?:\.\d+)*\.?\s+|[IVXLC]+\.?\s+)?(' + heading_alternatives + r')\s*$',
        re.IGNORECASE | re.MULTILINE,
    )

    # Pattern to find any section heading (used to detect the end of the methods section).
    # A generic section heading: line starting with optional numbering, then capitalized words.
    # We detect headings as lines that are relatively short, start with a capital letter or number,
    # and don't end with typical sentence-ending punctuation (period followed by lowercase).
    generic_heading_pattern = re.compile(
        r'^(?:\d+(?:\.\d+)*\.?\s+|[IVXLC]+\.?\s+)?[A-Z][A-Za-z\s:&,\-]+\s*$',
        re.MULTILINE,
    )

    # Find the first methods heading match
    match = methods_heading_pattern.search(full_text)
    if match is None:
        return None

    # Start extracting from after the heading line
    section_start = match.end()

    # Find the next section heading of equal or higher level after the methods section
    # We search for generic headings that appear after our methods heading
    remaining_text = full_text[section_start:]

    # Find the next heading in the remaining text
    next_heading_match = generic_heading_pattern.search(remaining_text)

    if next_heading_match:
        section_text = remaining_text[:next_heading_match.start()]
    else:
        # No next heading found — take everything until the end
        section_text = remaining_text

    # Clean up: strip leading/trailing whitespace
    section_text = section_text.strip()

    return section_text if section_text else None


def extract_dataset_links(full_text: str) -> list[dict]:
    """Extract dataset URLs from the paper text.

    Scans for URLs pointing to known dataset repositories (Zenodo, Figshare,
    GitHub, Kaggle, Dryad, Dataverse, OSF, etc.) as well as generic URLs
    that contain dataset-related keywords.

    Args:
        full_text: The full extracted text content of the paper.

    Returns:
        A list of dicts with keys: url, source (repository name), context (surrounding text).
    """
    if not full_text:
        return []

    # Known dataset repository domains
    dataset_domains = {
        "zenodo.org": "Zenodo",
        "figshare.com": "Figshare",
        "github.com": "GitHub",
        "kaggle.com": "Kaggle",
        "datadryad.org": "Dryad",
        "dryad.org": "Dryad",
        "dataverse.harvard.edu": "Harvard Dataverse",
        "dataverse.org": "Dataverse",
        "osf.io": "OSF",
        "data.mendeley.com": "Mendeley Data",
        "ieee-dataport.org": "IEEE DataPort",
        "pangaea.de": "PANGAEA",
        "openml.org": "OpenML",
        "huggingface.co": "Hugging Face",
        "archive.ics.uci.edu": "UCI ML Repository",
    }

    # Dataset-related keywords in URLs
    dataset_keywords = ["dataset", "data", "download", "repository", "supplement"]

    # Find all URLs in the text
    url_pattern = re.compile(
        r'https?://[^\s<>\"\'\)\]\},;]+',
        re.IGNORECASE,
    )

    found_links: list[dict] = []
    seen_urls: set[str] = set()

    for match in url_pattern.finditer(full_text):
        url = match.group(0).rstrip('.')  # Remove trailing periods

        # Deduplicate
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Check if URL matches a known dataset domain
        source = None
        for domain, name in dataset_domains.items():
            if domain in url.lower():
                source = name
                break

        # If not a known domain, check for dataset keywords in the URL
        if source is None:
            url_lower = url.lower()
            if any(kw in url_lower for kw in dataset_keywords):
                source = "Unknown Repository"
            else:
                continue  # Skip URLs that don't look like datasets

        # Extract surrounding context (50 chars before and after)
        start = max(0, match.start() - 80)
        end = min(len(full_text), match.end() + 80)
        context = full_text[start:end].replace("\n", " ").strip()

        found_links.append({
            "url": url,
            "source": source,
            "context": context,
        })

    return found_links


def extract_visual_assets(pdf_bytes: bytes) -> list[dict]:
    """Extract figures from a PDF using caption-anchored detection.

    Strategy: Find "Fig. X" / "Figure X" captions via text extraction,
    then extract the visual region above each caption by scanning upward
    for whitespace boundaries.

    Phase 1: Find figure captions using PyMuPDF text extraction
    Phase 2: Render page at 300 DPI, scan upward from caption to find figure bounds
    Phase 3: Crop the figure region (including caption)

    Args:
        pdf_bytes: Raw PDF file bytes.

    Returns:
        A list of dicts with page_number, width, height, and image_data (base64 PNG).
    """
    DPI = 300
    zoom = DPI / 72
    matrix = fitz.Matrix(zoom, zoom)

    # Caption detection pattern
    CAPTION_PATTERN = re.compile(
        r'(Extended\s+Data\s+)?Fig(ure)?\.?\s*\d+',
        re.IGNORECASE
    )

    # Whitespace detection parameters
    WHITE_THRESHOLD = 245
    WHITE_ROW_RATIO = 0.95
    MIN_GAP_HEIGHT = 8  # pixels — minimum whitespace band to count as boundary
    MAX_UPWARD_SEARCH = 2000  # pixels — max distance to search upward
    PADDING = 8  # pixels
    MIN_FIG_HEIGHT = 100  # pixels — minimum figure height to keep

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return []

    visual_assets: list[dict] = []

    try:
        for page_index in range(len(doc)):
            page_number = page_index + 1
            try:
                page = doc[page_index]

                # === Phase 1: Find figure captions ===
                captions = _find_figure_captions(page, CAPTION_PATTERN)

                if not captions:
                    continue

                # === Phase 2: Render page and extract figure regions ===
                pixmap = page.get_pixmap(matrix=matrix)
                img_height = pixmap.height
                img_width = pixmap.width

                # Convert to numpy array
                img_data = pixmap.samples
                n = pixmap.n
                if n == 4:
                    img_array = np.frombuffer(img_data, dtype=np.uint8).reshape(
                        img_height, img_width, 4
                    ).copy()
                    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
                elif n == 3:
                    img_array = np.frombuffer(img_data, dtype=np.uint8).reshape(
                        img_height, img_width, 3
                    ).copy()
                    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                else:
                    img_array = np.frombuffer(img_data, dtype=np.uint8).reshape(
                        img_height, img_width
                    ).copy()
                    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)

                gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

                # Process each caption
                for caption in captions:
                    try:
                        # Scale caption bbox to pixel coordinates at render DPI
                        cap_x0 = int(caption["bbox"][0] * zoom)
                        cap_y0 = int(caption["bbox"][1] * zoom)
                        cap_x1 = int(caption["bbox"][2] * zoom)
                        cap_y1 = int(caption["bbox"][3] * zoom)

                        # Figure region is ABOVE the caption
                        # Search upward from caption top to find whitespace boundary
                        fig_bottom = cap_y0  # top of caption = bottom of figure

                        # Determine horizontal bounds — use caption width but expand
                        # to capture full-width figures
                        fig_x0 = max(0, cap_x0 - 20)
                        fig_x1 = min(img_width, cap_x1 + 20)

                        # For two-column papers, figure might span the column
                        # Expand to check if figure is wider than caption
                        # Look at the row just above caption for content bounds
                        if fig_bottom > 10:
                            check_row = gray[fig_bottom - 10:fig_bottom, :]
                            col_has_content = np.any(check_row < 200, axis=0)
                            content_cols = np.where(col_has_content)[0]
                            if len(content_cols) > 0:
                                fig_x0 = max(0, int(content_cols[0]) - 10)
                                fig_x1 = min(img_width, int(content_cols[-1]) + 10)

                        # Search upward for whitespace boundary
                        fig_top = _find_top_boundary(
                            gray, fig_bottom, fig_x0, fig_x1,
                            WHITE_THRESHOLD, WHITE_ROW_RATIO,
                            MIN_GAP_HEIGHT, MAX_UPWARD_SEARCH
                        )

                        # Include caption in the crop
                        crop_bottom = min(img_height, cap_y1 + PADDING)

                        # Validate figure height
                        fig_height = crop_bottom - fig_top
                        if fig_height < MIN_FIG_HEIGHT:
                            continue

                        # Apply padding
                        crop_top = max(0, fig_top - PADDING)
                        crop_x0 = max(0, fig_x0 - PADDING)
                        crop_x1 = min(img_width, fig_x1 + PADDING)

                        # Crop from original image
                        crop = img_bgr[crop_top:crop_bottom, crop_x0:crop_x1]

                        if crop.shape[0] < 80 or crop.shape[1] < 100:
                            continue

                        # Encode as PNG
                        success, png_bytes = cv2.imencode(".png", crop)
                        if not success:
                            continue

                        image_data = base64.b64encode(png_bytes.tobytes()).decode("ascii")

                        visual_assets.append({
                            "page_number": page_number,
                            "width": crop.shape[1],
                            "height": crop.shape[0],
                            "image_data": image_data,
                        })
                    except Exception:
                        continue

            except Exception:
                continue
    finally:
        doc.close()

    return visual_assets


def _find_figure_captions(page, pattern) -> list[dict]:
    """Find figure captions on a page using text extraction.

    Searches for text matching "Fig. X", "Figure X", "Extended Data Fig. X" etc.
    Returns a list of dicts with 'text', 'bbox' (in PDF points), and 'label'.
    """
    captions = []
    text_dict = page.get_text("dict")

    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue

        block_text = ""
        block_bbox = block.get("bbox")

        for line in block.get("lines", []):
            for span in line.get("spans", []):
                block_text += span.get("text", "")

        block_text = block_text.strip()

        # Check if this block starts with a figure caption pattern
        match = pattern.match(block_text)
        if match:
            captions.append({
                "text": block_text[:100],  # first 100 chars
                "bbox": block_bbox,
                "label": match.group(0),
            })

    return captions


def _find_top_boundary(
    gray: np.ndarray,
    start_y: int,
    x0: int,
    x1: int,
    white_threshold: int,
    white_ratio: float,
    min_gap_height: int,
    max_search: int,
) -> int:
    """Scan upward from start_y to find the top boundary of a figure.

    Looks for a horizontal band of whitespace (rows where most pixels are white)
    within the x0-x1 column range. Returns the y coordinate of the figure top.
    """
    gap_count = 0
    search_limit = max(0, start_y - max_search)

    for y in range(start_y - 1, search_limit, -1):
        # Check if this row is mostly white in the figure's column range
        row = gray[y, x0:x1]
        if len(row) == 0:
            continue

        white_pixels = np.sum(row >= white_threshold)
        ratio = white_pixels / len(row)

        if ratio >= white_ratio:
            gap_count += 1
            if gap_count >= min_gap_height:
                # Found a whitespace band — figure top is just below it
                return y + min_gap_height
        else:
            gap_count = 0

    # No whitespace found — use the search limit
    return search_limit


def _cluster_rects(rects: list, margin: float = 5) -> list:
    """Cluster nearby rectangles into larger bounding regions.

    Groups rectangles that overlap or are within `margin` points of each other,
    returning the bounding box of each cluster.
    """
    if not rects:
        return []

    # Sort by y0 then x0
    sorted_rects = sorted(rects, key=lambda r: (r.y0, r.x0))
    clusters: list[fitz.Rect] = []

    for rect in sorted_rects:
        merged = False
        for i, cluster in enumerate(clusters):
            # Check if rect is near/overlapping this cluster
            expanded = fitz.Rect(
                cluster.x0 - margin,
                cluster.y0 - margin,
                cluster.x1 + margin,
                cluster.y1 + margin,
            )
            if expanded.intersects(rect):
                # Merge into this cluster
                clusters[i] = cluster | rect  # Union
                merged = True
                break
        if not merged:
            clusters.append(fitz.Rect(rect))

    # Second pass: merge clusters that now overlap after expansion
    changed = True
    while changed:
        changed = False
        new_clusters: list[fitz.Rect] = []
        for cluster in clusters:
            merged = False
            for i, existing in enumerate(new_clusters):
                expanded = fitz.Rect(
                    existing.x0 - margin,
                    existing.y0 - margin,
                    existing.x1 + margin,
                    existing.y1 + margin,
                )
                if expanded.intersects(cluster):
                    new_clusters[i] = existing | cluster
                    merged = True
                    changed = True
                    break
            if not merged:
                new_clusters.append(cluster)
        clusters = new_clusters

    return clusters


def _merge_overlapping_rects(rects: list, margin: float = 10) -> list:
    """Merge overlapping or nearby rectangles into unified regions."""
    if not rects:
        return []

    # Use the clustering approach
    return _cluster_rects(rects, margin=margin)


def run_extraction(paper_id: str) -> None:
    """Orchestrate full extraction pipeline for a given paper.

    Retrieves raw PDF bytes from the store, runs all extraction steps
    sequentially, and updates the store with results after each step.
    Sets status to 'complete' when all steps finish.

    Each step is wrapped in try/except so that partial results are always
    stored even if a later step fails.
    """
    from app.store import get_entry, update_entry

    entry = get_entry(paper_id)
    if entry is None:
        return

    raw_bytes = entry.get("raw_bytes")
    if raw_bytes is None:
        update_entry(paper_id, status="complete")
        return

    # Step 1: Extract metadata
    try:
        metadata = extract_metadata(raw_bytes)
        update_entry(paper_id, metadata=metadata)
    except Exception:
        update_entry(paper_id, metadata=None)

    # Step 2: Extract content
    content = None
    skipped_pages: list[int] = []
    try:
        content, skipped_pages = extract_content(raw_bytes)
        update_entry(paper_id, content=content, skipped_pages=skipped_pages)
    except Exception:
        update_entry(paper_id, content=None, skipped_pages=[])

    # Step 3: Extract research methods (uses extracted content)
    try:
        research_methods = extract_research_methods(content) if content else None
        update_entry(paper_id, research_methods=research_methods)
    except Exception:
        update_entry(paper_id, research_methods=None)

    # Step 4: Extract dataset links (uses extracted content)
    try:
        dataset_links = extract_dataset_links(content) if content else []
        update_entry(paper_id, dataset_links=dataset_links)
    except Exception:
        update_entry(paper_id, dataset_links=[])

    # Step 5: Extract visual assets
    try:
        visual_assets = extract_visual_assets(raw_bytes)
        update_entry(paper_id, visual_assets=visual_assets)
    except Exception:
        update_entry(paper_id, visual_assets=[])

    # Mark extraction as complete
    update_entry(paper_id, status="complete")
