# Implementation Plan: Academic Paper Critic — Extraction Pipeline

## Overview

Build the PDF extraction pipeline on the existing FastAPI backend. Replace the current upload route with a structured pipeline that validates uploads, generates paper IDs, runs extraction in a background task, stores results in-memory, and exposes a retrieval endpoint. The frontend integration updates the existing page to call the new endpoints and poll for results.

## Tasks

- [x] 1. Set up project structure, dependencies, and core data models
  - [x] 1.1 Update backend dependencies and create module files
    - Update `backend/requirements.txt`: replace `pdfplumber` and `pdf2image` with `PyMuPDF` (fitz), add `pydantic`, add `hypothesis` and `pytest` for testing
    - Create `backend/app/store.py` (empty placeholder)
    - Create `backend/app/extractor.py` (empty placeholder)
    - Create `backend/app/routes/papers.py` (empty placeholder)
    - Create `backend/app/models.py` (empty placeholder)
    - Create `backend/tests/` directory with `__init__.py`
    - _Requirements: 7.1, 7.2_

  - [x] 1.2 Implement Pydantic data models in `backend/app/models.py`
    - Define `Metadata` model with fields: title (str, max 500), authors (list[str], max 50), institutions (list[str], max 50), journal (Optional[str], max 300), date (Optional[str])
    - Define `VisualAsset` model with fields: page_number (int), width (int), height (int), image_data (str)
    - Define `PaperEntry` model with fields: paper_id (str), status (str), metadata (Optional[Metadata]), content (Optional[str]), skipped_pages (list[int]), research_methods (Optional[str]), visual_assets (list[VisualAsset])
    - Define `UploadResponse` model with field: paper_id (str)
    - Define `ErrorResponse` model with field: error (str)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 1.3 Implement the Paper Store in `backend/app/store.py`
    - Create module-level `_store: dict[str, dict[str, Any]]` and `_lock: Lock()`
    - Implement `create_entry(paper_id: str, raw_bytes: bytes)` — stores raw bytes with status "extracting" and all extraction fields as None
    - Implement `get_entry(paper_id: str) -> dict | None` — returns entry or None if not found
    - Implement `update_entry(paper_id: str, **fields)` — updates specified fields on existing entry
    - All operations must acquire `_lock` for thread safety
    - _Requirements: 1.2, 6.2, 6.3, 6.4, 7.6_

- [x] 2. Implement upload route with validation
  - [x] 2.1 Rewrite `backend/app/routes/upload.py` with validation and background task dispatch
    - Remove all existing code in the file
    - Implement `POST /api/upload` endpoint accepting multipart file upload
    - Validate: file is present and non-empty (reject with 400: "A non-empty PDF file is required")
    - Validate: file starts with `%PDF` magic bytes (reject with 400: "Only PDF files are supported")
    - Validate: file size ≤ 20 MB (reject with 400: "File exceeds the 20 MB size limit")
    - On valid upload: generate UUID v4, call `store.create_entry()`, enqueue `run_extraction` as BackgroundTask, return 202 with `{ "paper_id": "<uuid>" }`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [ ]* 2.2 Write property tests for upload validation (Properties 1-4)
    - **Property 1: Upload returns unique valid UUID v4**
    - **Property 2: Non-PDF bytes are rejected**
    - **Property 3: Oversized files are rejected**
    - **Property 4: Upload storage round-trip**
    - Create `backend/tests/test_upload_properties.py`
    - Use Hypothesis to generate random byte sequences and valid/invalid PDF-like inputs
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**

  - [ ]* 2.3 Write unit tests for upload edge cases
    - Create `backend/tests/test_upload.py`
    - Test: empty file upload returns 400
    - Test: zero-byte file returns 400
    - Test: non-PDF file (e.g., PNG) returns 400
    - Test: file exactly at 20 MB boundary is accepted
    - Test: file at 20 MB + 1 byte is rejected
    - Test: valid small PDF returns 202 with paper_id
    - _Requirements: 1.3, 1.4, 1.6_

- [ ] 3. Implement PDF extraction logic
  - [x] 3.1 Implement metadata extraction in `backend/app/extractor.py`
    - Implement `extract_metadata(pdf_bytes: bytes) -> dict | None`
    - Use PyMuPDF (fitz) to open PDF and read document metadata (title, author, etc.)
    - Parse author names into a list, extract institutions from first-page text heuristics
    - Extract journal name from metadata or first-page text
    - Extract and format date as ISO 8601 "YYYY-MM-DD" or None
    - Wrap in try/except: return None if extraction fails entirely
    - For individual fields that fail: set to None, populate others
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [x] 3.2 Implement content extraction in `backend/app/extractor.py`
    - Implement `extract_content(pdf_bytes: bytes) -> tuple[str | None, list[int]]`
    - Use PyMuPDF to iterate pages in order, extract text blocks per page
    - Concatenate text with double newline (`\n\n`) between paragraphs/blocks
    - Track pages where extraction fails (empty text) in `skipped_pages` list
    - If all pages fail: return (None, skipped_pages)
    - Otherwise: return (concatenated_text, skipped_pages)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 3.3 Implement research methods extraction in `backend/app/extractor.py`
    - Implement `extract_research_methods(full_text: str) -> str | None`
    - Define list of headings: "Methods", "Methodology", "Materials and Methods", "Research Methods", "Experimental Design", "Research Design"
    - Search full text for section headings matching any of the above (case-insensitive)
    - Extract text from matched heading to next section heading of equal/higher level
    - If multiple matches: use first encountered
    - If no match: return None
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 3.4 Implement visual assets extraction in `backend/app/extractor.py`
    - Implement `extract_visual_assets(pdf_bytes: bytes) -> list[dict]`
    - Use PyMuPDF to render each page as a pixmap at 150 DPI
    - Convert pixmap to PNG bytes, then base64-encode
    - Build VisualAsset dict with page_number (1-indexed), width, height, image_data
    - Wrap each page render in try/except: skip failed pages
    - Return list ordered by ascending page_number
    - If all pages fail: return empty list
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 3.5 Implement the orchestrator function `run_extraction(paper_id: str)` in `backend/app/extractor.py`
    - Retrieve raw bytes from Paper_Store using paper_id
    - Call `extract_metadata` → update store with result
    - Call `extract_content` → update store with content and skipped_pages
    - Call `extract_research_methods` (using extracted content) → update store
    - Call `extract_visual_assets` → update store
    - Set status to "complete" after all steps finish
    - Each step wrapped in try/except so partial results are always stored
    - _Requirements: 2.8, 3.2, 4.4, 5.5, 6.3_

- [x] 4. Checkpoint - Verify extraction pipeline
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement retrieval endpoint and wire routes
  - [x] 5.1 Implement `GET /api/papers/{paper_id}` in `backend/app/routes/papers.py`
    - If paper_id not found in store: return 404 with `{ "error": "Paper not found" }`
    - If paper_id found and status is "extracting": return 200 with status "extracting" and null fields
    - If paper_id found and status is "complete": return 200 with full PaperEntry data
    - Use Pydantic models for response serialization
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 5.2 Update `backend/app/main.py` to register new routes
    - Import and include `papers.router` with prefix `/api`
    - Ensure upload router still registered at `/api`
    - Remove old pdfplumber/pdf2image imports if any remain
    - _Requirements: 6.1_

  - [ ]* 5.3 Write property tests for store and retrieval (Properties 9-10)
    - **Property 9: Non-existent paper ID returns not-found error**
    - **Property 10: Response structure conforms to schema constraints**
    - Create `backend/tests/test_store_properties.py`
    - Use Hypothesis to generate random UUIDs and verify 404 behavior
    - Verify completed entries conform to schema constraints
    - **Validates: Requirements 6.2, 7.1, 7.2**

- [ ] 6. Implement extractor property tests
  - [ ]* 6.1 Write property tests for metadata extraction (Property 5)
    - **Property 5: Missing metadata fields default to null**
    - Create `backend/tests/test_extractor_properties.py`
    - Use Hypothesis to generate PDFs with varying metadata presence
    - Verify missing fields are null while present fields are populated
    - **Validates: Requirements 2.6**

  - [ ]* 6.2 Write property tests for content extraction (Property 6)
    - **Property 6: Text extraction preserves page order with paragraph boundaries**
    - Add to `backend/tests/test_extractor_properties.py`
    - Generate synthetic multi-page PDFs, verify page order and double-newline separators
    - **Validates: Requirements 3.1, 3.2, 3.3**

  - [ ]* 6.3 Write property tests for research methods extraction (Property 7)
    - **Property 7: Methods section detection is case-insensitive and extracts first match**
    - Add to `backend/tests/test_extractor_properties.py`
    - Generate text with headings in random cases, verify correct section extracted
    - **Validates: Requirements 4.1, 4.2, 4.3**

  - [ ]* 6.4 Write property tests for visual assets extraction (Property 8)
    - **Property 8: Visual assets are rendered with correct metadata and ordering**
    - Add to `backend/tests/test_extractor_properties.py`
    - Generate multi-page PDFs, verify output structure and ordering
    - **Validates: Requirements 5.1, 5.2, 5.3**

- [x] 7. Frontend integration
  - [x] 7.1 Update `frontend/src/app/page.tsx` to call upload endpoint and poll for results
    - On file upload: send `POST http://localhost:8000/api/upload` with file as FormData
    - Store returned `paper_id` in component state
    - Poll `GET http://localhost:8000/api/papers/{paper_id}` every 2 seconds until status is "complete"
    - Display extraction status in chat area ("Extracting..." → "Extraction complete")
    - On completion: show a summary message with metadata (title, authors) and page count
    - Handle errors: display error messages from backend in chat
    - _Requirements: 1.1, 6.1, 6.3_

- [ ] 8. Final checkpoint - End-to-end verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The existing `pdfplumber` and `pdf2image` dependencies are replaced by `PyMuPDF` (fitz) which handles both text extraction and page rendering in a single library without requiring poppler
- The frontend polling approach is simple and appropriate for a hackathon MVP

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["2.1", "3.1", "3.2"] },
    { "id": 3, "tasks": ["2.2", "2.3", "3.3", "3.4"] },
    { "id": 4, "tasks": ["3.5"] },
    { "id": 5, "tasks": ["5.1", "5.2"] },
    { "id": 6, "tasks": ["5.3", "6.1", "6.2", "6.3", "6.4"] },
    { "id": 7, "tasks": ["7.1"] }
  ]
}
```
