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
                return _clean_journal_name(value)

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
                    return _clean_journal_name(journal_match.group(1).strip())

                # Look for lines with volume/issue indicators
                if re.search(r'\bVol\.?\s*\d+', line, re.IGNORECASE):
                    # The journal name is likely the text before "Vol."
                    parts = re.split(r'\bVol\.?\s*\d+', line, flags=re.IGNORECASE)
                    if parts[0].strip():
                        return _clean_journal_name(parts[0].strip().rstrip(',').strip())

        return None
    except Exception:
        return None


def _clean_journal_name(name: str) -> str:
    """Clean up a journal name by removing trailing/leading artifacts."""
    # Remove trailing pipes, dashes, colons, semicolons, commas
    name = re.sub(r'[\s|:;\-,/\\]+$', '', name)
    # Remove leading pipes, dashes, colons, semicolons
    name = re.sub(r'^[\s|:;\-,/\\]+', '', name)
    # Collapse multiple spaces
    name = re.sub(r'\s{2,}', ' ', name)
    # Remove any remaining non-printable characters
    name = ''.join(c for c in name if c.isprintable())
    return name.strip()


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


def extract_dataset_content(dataset_links: list[dict], max_rows: int = 500) -> list[dict]:
    """Fetch and parse tabular data from dataset URLs (CSV/Excel).

    For each dataset link, attempts to download the file and parse it into
    rows and columns. Supports CSV, TSV, XLS, and XLSX files. Also handles
    GitHub raw URLs and Zenodo download redirects.

    Args:
        dataset_links: List of dicts from extract_dataset_links (url, source, context).
        max_rows: Maximum number of rows to keep per dataset (to limit memory).

    Returns:
        A list of dicts with keys: url, filename, columns, rows, num_rows, truncated, error.
    """
    import io
    import urllib.parse
    from pathlib import PurePosixPath

    try:
        import requests
        import pandas as pd
    except ImportError:
        return []

    TIMEOUT = 30  # seconds
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB limit

    # File extensions we can parse
    TABULAR_EXTENSIONS = {".csv", ".tsv", ".xls", ".xlsx", ".xlsm"}

    results: list[dict] = []

    for link in dataset_links:
        url = link.get("url", "")
        if not url:
            continue

        # Try to determine file type from URL path
        parsed = urllib.parse.urlparse(url)
        path = PurePosixPath(parsed.path)
        ext = path.suffix.lower()

        # GitHub: convert blob URLs to raw URLs
        if "github.com" in url and "/blob/" in url:
            url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
            parsed = urllib.parse.urlparse(url)
            path = PurePosixPath(parsed.path)
            ext = path.suffix.lower()

        # If the URL doesn't have a tabular extension, try a HEAD request to check content-type
        if ext not in TABULAR_EXTENSIONS:
            try:
                head_resp = requests.head(url, timeout=TIMEOUT, allow_redirects=True)
                content_type = head_resp.headers.get("Content-Type", "").lower()
                content_disp = head_resp.headers.get("Content-Disposition", "")

                # Check content-disposition for filename
                if "filename=" in content_disp:
                    fname = content_disp.split("filename=")[-1].strip('" ')
                    ext = PurePosixPath(fname).suffix.lower()

                # Check content-type
                if ext not in TABULAR_EXTENSIONS:
                    if "csv" in content_type or "text/csv" in content_type:
                        ext = ".csv"
                    elif "spreadsheet" in content_type or "excel" in content_type:
                        ext = ".xlsx"
                    elif "tab-separated" in content_type:
                        ext = ".tsv"
                    else:
                        # Not a tabular file we can parse
                        continue
            except Exception:
                continue

        # Download the file
        try:
            resp = requests.get(url, timeout=TIMEOUT, allow_redirects=True, stream=True)
            resp.raise_for_status()

            # Check size from headers
            content_length = int(resp.headers.get("Content-Length", 0))
            if content_length > MAX_FILE_SIZE:
                results.append({
                    "url": link["url"],
                    "filename": path.name or "unknown",
                    "columns": [],
                    "rows": [],
                    "num_rows": 0,
                    "truncated": False,
                    "error": f"File too large ({content_length // (1024*1024)} MB)",
                })
                continue

            file_bytes = resp.content
        except Exception as e:
            results.append({
                "url": link["url"],
                "filename": path.name or "unknown",
                "columns": [],
                "rows": [],
                "num_rows": 0,
                "truncated": False,
                "error": f"Download failed: {str(e)[:100]}",
            })
            continue

        # Parse the file into a DataFrame
        try:
            if ext == ".csv":
                df = pd.read_csv(io.BytesIO(file_bytes), encoding_errors="replace")
            elif ext == ".tsv":
                df = pd.read_csv(io.BytesIO(file_bytes), sep="\t", encoding_errors="replace")
            elif ext in (".xls", ".xlsx", ".xlsm"):
                df = pd.read_excel(io.BytesIO(file_bytes))
            else:
                continue

            # Clean up: drop fully empty rows/columns
            df = df.dropna(how="all").dropna(axis=1, how="all")

            num_rows = len(df)
            truncated = num_rows > max_rows
            if truncated:
                df = df.head(max_rows)

            # Convert to serializable format
            columns = [str(c) for c in df.columns.tolist()]
            rows = df.fillna("").values.tolist()
            # Convert numpy types to native Python types
            rows = [[str(cell) if not isinstance(cell, (int, float, str, bool)) else cell for cell in row] for row in rows]

            results.append({
                "url": link["url"],
                "filename": path.name or "unknown",
                "columns": columns,
                "rows": rows,
                "num_rows": num_rows,
                "truncated": truncated,
                "error": None,
            })

        except Exception as e:
            results.append({
                "url": link["url"],
                "filename": path.name or "unknown",
                "columns": [],
                "rows": [],
                "num_rows": 0,
                "truncated": False,
                "error": f"Parse failed: {str(e)[:100]}",
            })

    return results


def extract_visual_assets(pdf_bytes: bytes) -> list[dict]:
    """Extract figures from a PDF using DocLayout-YOLO for layout detection.

    Uses a YOLO model trained specifically on academic document layouts to
    detect figure regions. This handles vector graphics, composite figures,
    and multi-panel layouts correctly because it detects at the semantic level.

    Steps:
    1. Render each page at 300 DPI
    2. Run DocLayout-YOLO to detect 'figure' regions
    3. Crop each detected figure from the rendered page
    4. Optionally include the figure caption if detected nearby

    Args:
        pdf_bytes: Raw PDF file bytes.

    Returns:
        A list of dicts with page_number, width, height, and image_data (base64 PNG).
    """
    DPI = 300
    zoom = DPI / 72
    matrix = fitz.Matrix(zoom, zoom)

    CONFIDENCE_THRESHOLD = 0.3
    PADDING = 10  # pixels
    MIN_WIDTH = 100
    MIN_HEIGHT = 80

    # Load model (cached after first call)
    model = _get_doclayout_model()
    if model is None:
        return []

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

                # Render page
                pixmap = page.get_pixmap(matrix=matrix)
                img_height = pixmap.height
                img_width = pixmap.width

                # Convert to numpy array (RGB for YOLO)
                img_data = pixmap.samples
                n = pixmap.n
                if n == 4:
                    img_array = np.frombuffer(img_data, dtype=np.uint8).reshape(
                        img_height, img_width, 4
                    ).copy()
                    img_rgb = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
                elif n == 3:
                    img_array = np.frombuffer(img_data, dtype=np.uint8).reshape(
                        img_height, img_width, 3
                    ).copy()
                    img_rgb = img_array
                else:
                    img_array = np.frombuffer(img_data, dtype=np.uint8).reshape(
                        img_height, img_width
                    ).copy()
                    img_rgb = cv2.cvtColor(img_array, cv2.COLOR_GRAY2RGB)

                # Save temp image for YOLO inference
                import tempfile
                import os
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                    temp_path = f.name
                    cv2.imwrite(temp_path, cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR))

                try:
                    # Run inference
                    results = model.predict(
                        temp_path,
                        imgsz=1024,
                        conf=CONFIDENCE_THRESHOLD,
                        device='cpu',
                        verbose=False,
                    )
                finally:
                    os.unlink(temp_path)

                if not results or len(results) == 0:
                    continue

                result = results[0]
                boxes = result.boxes

                if boxes is None or len(boxes) == 0:
                    continue

                # Collect figure and caption boxes
                figure_boxes = []
                caption_boxes = []

                for i in range(len(boxes)):
                    cls_id = int(boxes.cls[i].item())
                    conf = float(boxes.conf[i].item())
                    xyxy = boxes.xyxy[i].cpu().numpy()

                    if cls_id == 3 and conf >= CONFIDENCE_THRESHOLD:  # figure
                        figure_boxes.append(xyxy)
                    elif cls_id == 4 and conf >= CONFIDENCE_THRESHOLD:  # figure_caption
                        caption_boxes.append(xyxy)

                # For each figure, optionally merge with its caption
                for fig_box in figure_boxes:
                    x1, y1, x2, y2 = fig_box

                    # Check if there's a caption directly below this figure
                    for cap_box in caption_boxes:
                        cx1, cy1, cx2, cy2 = cap_box
                        # Caption should be below the figure and horizontally overlapping
                        if cy1 >= y2 - 5 and cy1 <= y2 + 30:
                            # Check horizontal overlap
                            overlap = min(x2, cx2) - max(x1, cx1)
                            if overlap > (x2 - x1) * 0.3:
                                # Extend figure box to include caption
                                y2 = max(y2, cy2)
                                x1 = min(x1, cx1)
                                x2 = max(x2, cx2)
                                break

                    # Apply padding
                    crop_x1 = max(0, int(x1) - PADDING)
                    crop_y1 = max(0, int(y1) - PADDING)
                    crop_x2 = min(img_width, int(x2) + PADDING)
                    crop_y2 = min(img_height, int(y2) + PADDING)

                    w = crop_x2 - crop_x1
                    h = crop_y2 - crop_y1

                    if w < MIN_WIDTH or h < MIN_HEIGHT:
                        continue

                    # Crop from the rendered image (BGR for cv2.imencode)
                    img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
                    crop = img_bgr[crop_y1:crop_y2, crop_x1:crop_x2]

                    # Step 2: Split into sub-panels using whitespace projection
                    sub_panels = _split_by_whitespace_projection(crop)

                    for panel in sub_panels:
                        if panel.shape[0] < MIN_HEIGHT or panel.shape[1] < MIN_WIDTH:
                            continue

                        # Step 3: Classify the panel
                        panel_type = _classify_panel(panel)

                        # Discard "other" (leftover labels, fragments)
                        if panel_type == "other":
                            continue

                        success, png_bytes = cv2.imencode(".png", panel)
                        if not success:
                            continue

                        image_data = base64.b64encode(png_bytes.tobytes()).decode("ascii")

                        visual_assets.append({
                            "page_number": page_number,
                            "width": panel.shape[1],
                            "height": panel.shape[0],
                            "image_data": image_data,
                            "type": panel_type,
                        })

            except Exception:
                continue
    finally:
        doc.close()

    return visual_assets


# Cache the model globally so it's only loaded once
_doclayout_model = None


def _get_doclayout_model():
    """Load and cache the DocLayout-YOLO model."""
    global _doclayout_model
    if _doclayout_model is not None:
        return _doclayout_model

    try:
        from doclayout_yolo import YOLOv10
        from huggingface_hub import hf_hub_download

        model_path = hf_hub_download(
            repo_id='juliozhao/DocLayout-YOLO-DocStructBench',
            filename='doclayout_yolo_docstructbench_imgsz1024.pt',
        )
        _doclayout_model = YOLOv10(model_path)
        return _doclayout_model
    except Exception:
        return None


def _split_into_subpanels(figure_img: np.ndarray) -> list[np.ndarray]:
    """Fallback: return figure as-is (splitting is now done via _split_by_labels)."""
    return [figure_img]


def _find_panel_labels_from_pdf(
    page, crop_x1: int, crop_y1: int, crop_x2: int, crop_y2: int, zoom: float
) -> list[dict]:
    """Unused ??? kept for compatibility."""
    return []


def _split_by_labels(
    figure_img: np.ndarray, labels: list[dict]
) -> list[np.ndarray]:
    """Split a figure into sub-panels by finding cut lines through pure whitespace.

    Strategy:
    1. Convert to grayscale, threshold to find all content (dark pixels)
    2. Project content onto x-axis (column projection) and y-axis (row projection)
    3. Find valleys (runs of zero/near-zero) in both projections
    4. These valleys are whitespace bands where we can safely cut
    5. Use the valleys to define a grid of rectangles
    6. Each rectangle that contains significant content becomes a sub-panel

    This ensures we ONLY cut through whitespace ??? never through content.

    Args:
        figure_img: BGR numpy array of the figure.
        labels: Unused (kept for API compatibility).

    Returns:
        List of BGR numpy arrays, one per panel.
    """
    return _split_by_whitespace_projection(figure_img)


def _split_by_whitespace_projection(figure_img: np.ndarray) -> list[np.ndarray]:
    """Split a figure into sub-panels.

    Strategy:
    1. First pass: strict 100% white recursive split
    2. For each resulting piece, check if it contains MULTIPLE graphs
       (detected by finding multiple axis/number regions)
    3. Only apply relaxed splitting on pieces that have multiple graphs

    This avoids over-splitting single graphs while still breaking apart
    multi-graph panels.
    """
    h, w = figure_img.shape[:2]

    if h < 200 or w < 200:
        return [figure_img]

    # Step 1: Strict recursive split (100% white lines only)
    pieces = _recursive_split(figure_img, max_depth=4, depth=0)

    # Step 2: For each piece, check if it contains multiple graphs
    # Only apply relaxed split on those
    refined = []
    for piece in pieces:
        ph, pw = piece.shape[:2]
        if ph < 200 or pw < 200:
            refined.append(piece)
            continue

        # Count how many separate axis/number regions exist in this piece
        num_graphs = _count_graph_regions(piece)

        if num_graphs >= 4:
            # This piece has many graphs ??? try relaxed split
            sub = _recursive_split_relaxed(piece, max_depth=2, depth=0)
            refined.extend(sub)
        else:
            refined.append(piece)

    # Step 3: Merge small fragments
    panels = _merge_small_fragments(refined, figure_img)

    if len(panels) <= 1:
        return [figure_img]

    return panels


def _count_graph_regions(img: np.ndarray) -> int:
    """Count how many separate graphs exist by detecting distinct axis lines.

    Uses HoughLinesP to find long straight black lines (axes).
    Clusters them by position to count distinct graphs.

    A graph typically has:
    - A horizontal axis line (x-axis) in its lower portion
    - A vertical axis line (y-axis) on its left side

    Multiple horizontal axes at different y-positions = multiple graphs stacked.
    Multiple vertical axes at different x-positions = multiple graphs side by side.

    Returns: estimated number of separate graphs.
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Threshold to get only very dark pixels (black lines)
    _, binary = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY_INV)

    # Detect lines using HoughLinesP
    # Minimum line length: 20% of the smaller dimension
    min_line_len = int(min(h, w) * 0.15)

    lines = cv2.HoughLinesP(binary, 1, np.pi / 180, threshold=80,
                             minLineLength=min_line_len, maxLineGap=5)

    if lines is None:
        return 1

    # Separate into horizontal and vertical lines
    h_axes_y = []  # y-positions of horizontal axis lines
    v_axes_x = []  # x-positions of vertical axis lines

    for line in lines:
        x1, y1, x2, y2 = line[0]
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        length = (dx**2 + dy**2) ** 0.5

        # Horizontal line: nearly flat, long enough
        if dy < 5 and dx > min_line_len:
            h_axes_y.append((y1 + y2) // 2)

        # Vertical line: nearly vertical, long enough
        elif dx < 5 and dy > min_line_len:
            v_axes_x.append((x1 + x2) // 2)

    # Cluster horizontal axes by y-position
    # Two axes must be at least 15% of height apart to be different graphs
    h_clusters = _cluster_positions(h_axes_y, threshold=h * 0.15)

    # Cluster vertical axes by x-position
    v_clusters = _cluster_positions(v_axes_x, threshold=w * 0.15)

    # Number of graphs = max of horizontal or vertical axis count
    return max(len(h_clusters), len(v_clusters), 1)


def _cluster_positions(positions: list, threshold: float) -> list:
    """Cluster nearby positions into groups."""
    if not positions:
        return []

    sorted_pos = sorted(set(positions))
    clusters = [[sorted_pos[0]]]

    for p in sorted_pos[1:]:
        if p - clusters[-1][-1] < threshold:
            clusters[-1].append(p)
        else:
            clusters.append([p])

    return clusters


def _merge_small_fragments(
    pieces: list[np.ndarray], original: np.ndarray
) -> list[np.ndarray]:
    """Merge small fragments (labels, titles, axis text) with their nearest panel.

    A fragment is "small" if:
    - Its area is less than 15% of the average panel area, OR
    - It's very narrow (width < 25% of average) or very short (height < 25% of average)

    Small fragments get merged with the nearest larger panel by expanding
    that panel's crop to include the fragment.
    """
    if len(pieces) <= 1:
        return pieces

    # Calculate areas and dimensions
    areas = [p.shape[0] * p.shape[1] for p in pieces]
    heights = [p.shape[0] for p in pieces]
    widths = [p.shape[1] for p in pieces]

    # Determine what counts as a "real panel" vs a "fragment"
    # Use median to be robust against outliers
    sorted_areas = sorted(areas)
    median_area = sorted_areas[len(sorted_areas) // 2]
    median_h = sorted(heights)[len(heights) // 2]
    median_w = sorted(widths)[len(widths) // 2]

    # Classify each piece
    MIN_AREA_RATIO = 0.15  # must be at least 15% of median area
    MIN_DIM_RATIO = 0.25   # must be at least 25% of median dimension

    is_panel = []
    for i, p in enumerate(pieces):
        area_ok = areas[i] >= median_area * MIN_AREA_RATIO
        h_ok = heights[i] >= median_h * MIN_DIM_RATIO
        w_ok = widths[i] >= median_w * MIN_DIM_RATIO
        is_panel.append(area_ok and h_ok and w_ok)

    # If everything is a panel or everything is a fragment, return as-is
    panel_count = sum(is_panel)
    if panel_count == 0 or panel_count == len(pieces):
        return pieces

    # Return only the real panels (fragments are part of the panel they were split from)
    # Since we can't easily re-merge spatially without tracking positions,
    # just filter out the tiny fragments
    result = [p for i, p in enumerate(pieces) if is_panel[i]]

    return result if result else pieces


def _classify_panel(panel: np.ndarray) -> str:
    """Classify a panel as 'chart', 'image', or 'other'.

    Logic:
    1. If mostly text ??? 'other' (discard)
    2. If high-resolution continuous tones (not a simple drawing) ??? 'image'
    3. Otherwise it's a graph candidate:
       - If it has labels/scales with numbers ??? 'chart' (keep)
       - If no labels/numbers detected ??? 'other' (unlabeled graph, discard)

    Returns: 'chart', 'image', or 'other'
    """
    h, w = panel.shape[:2]
    area = h * w

    gray = cv2.cvtColor(panel, cv2.COLOR_BGR2GRAY)

    WHITE_THRESH = 235
    content_mask = gray < WHITE_THRESH
    content_pixels = np.sum(content_mask)
    content_ratio = content_pixels / area

    # Too little content = fragment
    if content_ratio < 0.03:
        return "other"

    # === Step 1: Is it mostly text? ===
    _, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        text_like_area = 0
        total_contour_area = 0
        for c in contours:
            x, y, cw, ch = cv2.boundingRect(c)
            ca = cv2.contourArea(c)
            total_contour_area += ca
            # Text characters: small, wide-ish, consistent height
            if ch < h * 0.06 and cw < w * 0.2 and ch > 3 and cw > 2:
                text_like_area += ca

        if total_contour_area > 0:
            text_ratio = text_like_area / total_contour_area
            # If >65% of content is text-shaped, it's text-only
            if text_ratio > 0.65 and content_ratio < 0.30:
                return "other"

    # === Step 2: Is it a high-resolution image (photo, microscopy, scan)? ===
    # Images have: many unique gray values, high content fill, continuous tones
    interior = gray[int(h * 0.1):int(h * 0.9), int(w * 0.1):int(w * 0.9)]
    is_image = False

    if interior.size > 100:
        unique_grays = len(np.unique(interior))
        white_ratio = np.sum(gray >= WHITE_THRESH) / area

        # High tonal range + fills most of the area + not mostly white
        if unique_grays > 100 and content_ratio > 0.45 and white_ratio < 0.45:
            is_image = True

        # Also check: if very few white pixels and lots of color variation
        if not is_image and white_ratio < 0.25 and unique_grays > 80:
            is_image = True

        # Gray background fills (like microscopy with gray bg)
        if not is_image and content_ratio > 0.7 and unique_grays > 60:
            is_image = True

    if is_image:
        return "image"

    # === Step 3: It's a graph candidate. Does it have labels/scales with numbers? ===
    # Must have BOTH: numbers on axes AND actual axis lines AND substantial plot area
    has_numbers = _detect_number_labels(gray, h, w)
    has_axes = _detect_axis_lines(gray, h, w)
    has_plot_content = _has_substantial_plot_area(gray, h, w)

    if has_numbers and has_axes and has_plot_content:
        return "chart"

    # No proper chart structure ??? discard
    return "other"


def _detect_number_labels(gray: np.ndarray, h: int, w: int) -> bool:
    """Detect if a panel has numeric axis labels/scales using OCR.

    Runs OCR on the bottom and left edge strips to find actual numbers.
    Numbers must be at least 2 digits found in the axis region.

    Returns True if numeric labels are detected.
    """
    import pytesseract

    config = '--psm 6 -c tessedit_char_whitelist=0123456789.,-'

    # Check bottom strip (x-axis labels) ??? bottom 18%
    bottom_strip = gray[int(h * 0.82):, :]
    if bottom_strip.size > 0 and bottom_strip.shape[0] > 10:
        try:
            _, bw = cv2.threshold(bottom_strip, 180, 255, cv2.THRESH_BINARY)
            text = pytesseract.image_to_string(bw, config=config).strip()
            digits = sum(1 for c in text if c.isdigit())
            if digits >= 2:
                return True
        except Exception:
            pass

    # Check left strip (y-axis labels) ??? left 18%
    left_strip = gray[:, :int(w * 0.18)]
    if left_strip.size > 0 and left_strip.shape[1] > 10:
        try:
            _, bw = cv2.threshold(left_strip, 180, 255, cv2.THRESH_BINARY)
            text = pytesseract.image_to_string(bw, config=config).strip()
            digits = sum(1 for c in text if c.isdigit())
            if digits >= 2:
                return True
        except Exception:
            pass

    return False


def _detect_axis_lines(gray: np.ndarray, h: int, w: int) -> bool:
    """Detect if a panel has axis lines (L-shape: horizontal bottom + vertical left).

    A real chart axis is a strong straight line spanning a significant portion
    of the panel. Must find at least one axis line.

    Returns True if axis lines are detected.
    """
    edges = cv2.Canny(gray, 50, 150)

    # Check for horizontal axis line in bottom half
    # (between 50-90% height, spanning at least 30% of width)
    bottom_region = edges[int(h * 0.5):int(h * 0.92), int(w * 0.1):int(w * 0.9)]
    has_h_axis = False
    if bottom_region.size > 0:
        # Project onto rows ??? a strong horizontal line creates a peak
        h_proj = np.sum(bottom_region > 0, axis=1)
        effective_width = int(w * 0.8)
        if np.max(h_proj) > effective_width * 0.3:
            has_h_axis = True

    # Check for vertical axis line in left quarter
    # (between 10-90% height, in left 5-30% of width)
    left_region = edges[int(h * 0.1):int(h * 0.9), int(w * 0.05):int(w * 0.3)]
    has_v_axis = False
    if left_region.size > 0:
        v_proj = np.sum(left_region > 0, axis=0)
        effective_height = int(h * 0.8)
        if np.max(v_proj) > effective_height * 0.3:
            has_v_axis = True

    # Need at least one axis line
    return has_h_axis or has_v_axis


def _has_substantial_plot_area(gray: np.ndarray, h: int, w: int) -> bool:
    """Check if the panel has a substantial plot/data area (not just a label with a line).

    A real chart has content in the interior (between the axes), not just
    at the edges. Checks that the central region has meaningful data.

    Returns True if there's substantial plot content.
    """
    WHITE_THRESH = 235

    # Check the interior region (between where axes would be and the edges)
    # This is roughly the "plot area" ??? between 15-80% width and 10-75% height
    interior = gray[int(h * 0.1):int(h * 0.75), int(w * 0.15):int(w * 0.85)]

    if interior.size == 0:
        return False

    # Content in the interior
    interior_content = np.sum(interior < WHITE_THRESH) / interior.size

    # A real chart has data in the plot area (bars, lines, points, etc.)
    # Just a label with a line would have very little interior content
    # Require at least 3% of the interior to have content
    if interior_content < 0.03:
        return False

    # Also check that the panel is big enough to be a real chart
    # (not just a tiny fragment with a line and some text)
    if h < 150 and w < 150:
        return False

    return True


def _recursive_split(
    img: np.ndarray, max_depth: int, depth: int
) -> list[np.ndarray]:
    """Recursively split an image by alternating horizontal and vertical cuts."""
    h, w = img.shape[:2]
    MIN_PANEL = 80
    WHITE_THRESH = 240
    MIN_GAP = 6
    MARGIN_RATIO = 0.02

    if h < MIN_PANEL or w < MIN_PANEL or depth >= max_depth:
        return [img]

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

    margin_h = int(h * MARGIN_RATIO)
    margin_w = int(w * MARGIN_RATIO)

    # Try horizontal split first, then vertical
    # Alternate based on depth: even=horizontal first, odd=vertical first
    if depth % 2 == 0:
        axes = ['horizontal', 'vertical']
    else:
        axes = ['vertical', 'horizontal']

    for axis in axes:
        if axis == 'horizontal':
            # Find rows that are 100% white
            gaps = []
            in_gap = False
            gap_start = 0
            for y in range(h):
                is_white = np.all(gray[y, :] >= WHITE_THRESH)
                if is_white:
                    if not in_gap:
                        gap_start = y
                        in_gap = True
                else:
                    if in_gap:
                        if y - gap_start >= MIN_GAP and gap_start > margin_h and y < h - margin_h:
                            gaps.append((gap_start, y))
                        in_gap = False

            if gaps:
                # Split at gap midpoints
                cuts = [0] + [int((g[0] + g[1]) / 2) for g in gaps] + [h]
                strips = []
                for i in range(len(cuts) - 1):
                    y1, y2 = cuts[i], cuts[i + 1]
                    if y2 - y1 >= MIN_PANEL:
                        strips.append(img[y1:y2, :])

                if len(strips) > 1:
                    # Recursively split each strip
                    results = []
                    for strip in strips:
                        results.extend(_recursive_split(strip, max_depth, depth + 1))
                    return results

        else:  # vertical
            # Find columns that are 100% white
            gaps = []
            in_gap = False
            gap_start = 0
            for x in range(w):
                is_white = np.all(gray[:, x] >= WHITE_THRESH)
                if is_white:
                    if not in_gap:
                        gap_start = x
                        in_gap = True
                else:
                    if in_gap:
                        if x - gap_start >= MIN_GAP and gap_start > margin_w and x < w - margin_w:
                            gaps.append((gap_start, x))
                        in_gap = False

            if gaps:
                cuts = [0] + [int((g[0] + g[1]) / 2) for g in gaps] + [w]
                strips = []
                for i in range(len(cuts) - 1):
                    x1, x2 = cuts[i], cuts[i + 1]
                    if x2 - x1 >= MIN_PANEL:
                        strips.append(img[:, x1:x2])

                if len(strips) > 1:
                    results = []
                    for strip in strips:
                        results.extend(_recursive_split(strip, max_depth, depth + 1))
                    return results

    # No splits found on either axis
    return [img]


def _recursive_split_relaxed(
    img: np.ndarray, max_depth: int, depth: int
) -> list[np.ndarray]:
    """Relaxed split for oversized panels.

    For horizontal cuts: checks if the central 85% of each row is white
    (skips left 10% where panel labels sit and right 5%).
    For vertical cuts: checks if the central 70% of each column is white
    (skips top/bottom where titles and shared labels sit).

    Uses 98% white threshold (allows minor anti-aliasing).
    """
    h, w = img.shape[:2]
    MIN_PANEL = 100
    WHITE_THRESH = 235
    WHITE_RATIO = 0.98
    MIN_GAP = 12
    MARGIN_RATIO = 0.04

    if h < MIN_PANEL or w < MIN_PANEL or depth >= max_depth:
        return [img]

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

    margin_h = int(h * MARGIN_RATIO)
    margin_w = int(w * MARGIN_RATIO)

    # Try both axes
    for axis in ['horizontal', 'vertical']:
        if axis == 'horizontal':
            # For horizontal cuts: check central 85% of each row
            # Skip left 10% (panel labels) and right 5%
            x_start = int(w * 0.10)
            x_end = int(w * 0.95)
            check_width = x_end - x_start

            if check_width < 50:
                continue

            gaps = []
            in_gap = False
            gap_start = 0
            for y in range(h):
                row_section = gray[y, x_start:x_end]
                white_ratio = np.sum(row_section >= WHITE_THRESH) / check_width
                if white_ratio >= WHITE_RATIO:
                    if not in_gap:
                        gap_start = y
                        in_gap = True
                else:
                    if in_gap:
                        if y - gap_start >= MIN_GAP and gap_start > margin_h and y < h - margin_h:
                            gaps.append((gap_start, y))
                        in_gap = False

            if gaps:
                cuts = [0] + [int((g[0] + g[1]) / 2) for g in gaps] + [h]
                strips = []
                for i in range(len(cuts) - 1):
                    y1, y2 = cuts[i], cuts[i + 1]
                    if y2 - y1 >= MIN_PANEL:
                        strips.append(img[y1:y2, :])

                if len(strips) > 1:
                    results = []
                    for strip in strips:
                        results.extend(_recursive_split_relaxed(strip, max_depth, depth + 1))
                    return results

        else:  # vertical
            # For vertical cuts: check central 70% of each column
            y_start = int(h * 0.15)
            y_end = int(h * 0.85)
            check_height = y_end - y_start

            if check_height < 50:
                continue

            gaps = []
            in_gap = False
            gap_start = 0
            for x in range(w):
                col_section = gray[y_start:y_end, x]
                white_ratio = np.sum(col_section >= WHITE_THRESH) / check_height
                if white_ratio >= WHITE_RATIO:
                    if not in_gap:
                        gap_start = x
                        in_gap = True
                else:
                    if in_gap:
                        if x - gap_start >= MIN_GAP and gap_start > margin_w and x < w - margin_w:
                            gaps.append((gap_start, x))
                        in_gap = False

            if gaps:
                cuts = [0] + [int((g[0] + g[1]) / 2) for g in gaps] + [w]
                strips = []
                for i in range(len(cuts) - 1):
                    x1, x2 = cuts[i], cuts[i + 1]
                    if x2 - x1 >= MIN_PANEL:
                        strips.append(img[:, x1:x2])

                if len(strips) > 1:
                    results = []
                    for strip in strips:
                        results.extend(_recursive_split_relaxed(strip, max_depth, depth + 1))
                    return results

    return [img]


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
    update_entry(paper_id, current_step="Extracting metadata...")
    try:
        metadata = extract_metadata(raw_bytes)
        update_entry(paper_id, metadata=metadata)
    except Exception:
        update_entry(paper_id, metadata=None)

    # Step 2: Extract content
    update_entry(paper_id, current_step="Extracting text content...")
    content = None
    skipped_pages: list[int] = []
    try:
        content, skipped_pages = extract_content(raw_bytes)
        update_entry(paper_id, content=content, skipped_pages=skipped_pages)
    except Exception:
        update_entry(paper_id, content=None, skipped_pages=[])

    # Step 3: Extract research methods (uses extracted content)
    update_entry(paper_id, current_step="Analyzing research methods...")
    try:
        research_methods = extract_research_methods(content) if content else None
        update_entry(paper_id, research_methods=research_methods)
    except Exception:
        update_entry(paper_id, research_methods=None)

    # Step 4: Extract dataset links (uses extracted content)
    update_entry(paper_id, current_step="Finding dataset links...")
    dataset_links = []
    try:
        dataset_links = extract_dataset_links(content) if content else []
        update_entry(paper_id, dataset_links=dataset_links)
    except Exception:
        update_entry(paper_id, dataset_links=[])

    # Step 4b: Parse uploaded dataset file if present
    update_entry(paper_id, current_step="Parsing dataset file...")
    try:
        dataset_file = entry.get("dataset_file")
        if dataset_file:
            import io
            import pandas as pd
            from pathlib import PurePosixPath

            filename = dataset_file["filename"]
            file_bytes = dataset_file["bytes"]
            ext = PurePosixPath(filename).suffix.lower()

            df = None
            if ext == ".csv":
                df = pd.read_csv(io.BytesIO(file_bytes), encoding_errors="replace")
            elif ext == ".tsv":
                df = pd.read_csv(io.BytesIO(file_bytes), sep="\t", encoding_errors="replace")
            elif ext in (".xls", ".xlsx", ".xlsm"):
                df = pd.read_excel(io.BytesIO(file_bytes))

            if df is not None:
                df = df.dropna(how="all").dropna(axis=1, how="all")
                num_rows = len(df)
                max_rows = 500
                truncated = num_rows > max_rows
                if truncated:
                    df = df.head(max_rows)

                columns = [str(c) for c in df.columns.tolist()]
                rows = df.fillna("").values.tolist()
                rows = [
                    [str(cell) if not isinstance(cell, (int, float, str, bool)) else cell for cell in row]
                    for row in rows
                ]

                update_entry(paper_id, datasets=[{
                    "url": f"uploaded://{filename}",
                    "filename": filename,
                    "columns": columns,
                    "rows": rows,
                    "num_rows": num_rows,
                    "truncated": truncated,
                    "error": None,
                }])
            else:
                update_entry(paper_id, datasets=[])
        else:
            update_entry(paper_id, datasets=[])
    except Exception:
        update_entry(paper_id, datasets=[])

    # Step 5: Extract visual assets
    update_entry(paper_id, current_step="Detecting figures and charts...")
    try:
        visual_assets = extract_visual_assets(raw_bytes)
        update_entry(paper_id, visual_assets=visual_assets)
    except Exception:
        update_entry(paper_id, visual_assets=[])

    # Step 6: Run evaluation modules (AI image detection, predatory check, MNCS, cherry picking, graph analysis)
    try:
        from app.evaluator import run_evaluation
        run_evaluation(paper_id)
    except Exception:
        pass

    # Mark extraction as complete
    update_entry(paper_id, status="complete")
