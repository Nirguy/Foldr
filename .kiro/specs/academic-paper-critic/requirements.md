# Requirements Document

## Introduction

Foldr's Academic Paper Critic feature begins with robust PDF reading and extraction. The system accepts an uploaded PDF academic paper and extracts structured data across four categories: metadata, content, research methods, and visual assets. Extracted data is stored in-memory keyed by a generated paper ID for fast retrieval during the demo. This is a hackathon MVP prioritizing simplicity and speed of development.

## Glossary

- **Foldr**: The web application consisting of a Next.js frontend and Python FastAPI backend
- **Upload_Service**: The backend component responsible for receiving PDF files and generating a paper ID
- **PDF_Extractor**: The backend component that parses PDF files to extract text and images
- **Paper_Store**: An in-memory dictionary on the backend that holds extracted paper data keyed by paper ID
- **Paper_ID**: A unique identifier generated for each uploaded paper, used to retrieve extraction results
- **Metadata**: Structured information about the paper including title, authors, institutions, journal, and date
- **Content**: The full extracted text of the paper as a single string
- **Research_Methods**: The extracted methodology section text describing how the research was conducted
- **Visual_Assets**: Graphs, figures, and images extracted from the paper as base64-encoded PNGs

## Requirements

### Requirement 1: PDF Upload and Storage

**User Story:** As a user, I want to upload a PDF academic paper and receive a paper ID, so that I can later retrieve the extracted data.

#### Acceptance Criteria

1. WHEN a user uploads a PDF file, THE Upload_Service SHALL accept the file and return a generated Paper_ID as a UUID v4 string.
2. WHEN a PDF is accepted, THE Upload_Service SHALL store the raw PDF bytes in the Paper_Store keyed by the Paper_ID.
3. IF a user uploads a file whose content does not begin with the PDF magic bytes (%PDF), THEN THE Upload_Service SHALL reject the file and return an error message indicating only PDF files are supported.
4. IF a user uploads a PDF file larger than 20 MB, THEN THE Upload_Service SHALL reject the file and return an error message indicating the file exceeds the size limit.
5. THE Upload_Service SHALL generate a unique Paper_ID in UUID v4 format for each uploaded file.
6. IF a user submits an upload request with no file attached or with an empty file of zero bytes, THEN THE Upload_Service SHALL reject the request and return an error message indicating that a non-empty PDF file is required.

### Requirement 2: Metadata Extraction

**User Story:** As a user, I want the system to extract metadata from my uploaded paper, so that I can see basic information about the paper at a glance.

#### Acceptance Criteria

1. WHEN a PDF is stored in the Paper_Store, THE PDF_Extractor SHALL extract the paper title from the document.
2. WHEN a PDF is stored in the Paper_Store, THE PDF_Extractor SHALL extract author names as they appear in the document.
3. WHEN a PDF is stored in the Paper_Store, THE PDF_Extractor SHALL extract institution names associated with the authors.
4. WHEN a PDF is stored in the Paper_Store, THE PDF_Extractor SHALL extract the journal name if present in the document.
5. WHEN a PDF is stored in the Paper_Store, THE PDF_Extractor SHALL extract the publication date if present in the document and store it in ISO 8601 date format (YYYY-MM-DD).
6. IF the PDF_Extractor cannot identify a specific metadata field, THEN THE PDF_Extractor SHALL set that field to null and proceed with available data.
7. IF the PDF is entirely unparseable and no metadata can be extracted, THEN THE PDF_Extractor SHALL set the entire Metadata object to null in the Paper_Store.
8. WHEN metadata extraction is complete, THE PDF_Extractor SHALL store the Metadata object in the Paper_Store under the corresponding Paper_ID.

### Requirement 3: Content Extraction

**User Story:** As a user, I want the system to extract the full text content from my paper, so that it can be analyzed for arguments and conclusions later.

#### Acceptance Criteria

1. WHEN a PDF is stored in the Paper_Store, THE PDF_Extractor SHALL extract the full text content from all pages of the document in sequential page order (page 1 through the last page).
2. WHEN text extraction is complete, THE PDF_Extractor SHALL store the Content as a single concatenated string in the Paper_Store under the corresponding Paper_ID.
3. THE PDF_Extractor SHALL preserve paragraph boundaries in the extracted Content by separating distinct text blocks with a double newline character sequence.
4. IF the PDF_Extractor cannot extract text from a page, THEN THE PDF_Extractor SHALL skip that page, continue extraction from remaining pages, and include the skipped page number in a list of skipped pages stored alongside the Content in the Paper_Store.
5. IF the PDF_Extractor cannot extract text from any page in the document, THEN THE PDF_Extractor SHALL set the Content field to null in the Paper_Store under the corresponding Paper_ID.

### Requirement 4: Research Methods Extraction

**User Story:** As a user, I want the system to extract the research methods section separately, so that it can later be evaluated for reliability, extensiveness, and relevance.

#### Acceptance Criteria

1. WHEN a PDF is stored in the Paper_Store, THE PDF_Extractor SHALL identify the research methods section by searching for section headings matching any of the following (case-insensitive): "Methods", "Methodology", "Materials and Methods", "Research Methods", "Experimental Design", or "Research Design".
2. WHEN a methods section heading is identified, THE PDF_Extractor SHALL extract all text from that heading up to the next section heading of equal or higher level.
3. IF multiple candidate methods sections are found, THEN THE PDF_Extractor SHALL extract the first matching section encountered in document order.
4. WHEN the methods section is identified, THE PDF_Extractor SHALL store the Research_Methods text in the Paper_Store under the corresponding Paper_ID.
5. IF the PDF_Extractor cannot identify a section heading matching the defined methods headings, THEN THE PDF_Extractor SHALL set the Research_Methods field to null and proceed.

### Requirement 5: Visual Assets Extraction

**User Story:** As a user, I want the system to extract graphs and figures from the paper, so that they can later be checked for misleading practices.

#### Acceptance Criteria

1. WHEN a PDF is stored in the Paper_Store, THE PDF_Extractor SHALL render each page as a PNG image at 150 DPI.
2. WHEN page renders are complete, THE PDF_Extractor SHALL store each rendered page as a base64-encoded PNG in the Visual_Assets list, ordered by ascending page number.
3. WHEN a page is rendered, THE PDF_Extractor SHALL record the page number (1-indexed integer), width in pixels, and height in pixels alongside the image data.
4. IF page rendering fails for a specific page, THEN THE PDF_Extractor SHALL skip that page, exclude it from the Visual_Assets list, and continue rendering remaining pages.
5. WHEN all extraction is complete, THE PDF_Extractor SHALL store the Visual_Assets list in the Paper_Store under the corresponding Paper_ID.
6. IF no pages are successfully rendered from the PDF, THEN THE PDF_Extractor SHALL store an empty Visual_Assets list in the Paper_Store under the corresponding Paper_ID.

### Requirement 6: Extraction Results Retrieval

**User Story:** As a user, I want to retrieve the extracted data by paper ID, so that the frontend can display extraction results and later pass them to analysis.

#### Acceptance Criteria

1. WHEN a client requests extraction results with a Paper_ID that exists in the Paper_Store and extraction is complete, THE Paper_Store SHALL return the extracted data including Metadata, Content, Research_Methods, and Visual_Assets within 2 seconds, where fields that could not be extracted are represented as null.
2. IF a client requests results with a Paper_ID that does not exist in the Paper_Store, THEN THE Paper_Store SHALL return an error indicating the paper was not found.
3. IF a client requests results with a Paper_ID that exists but extraction is not yet complete, THEN THE Paper_Store SHALL return a response indicating extraction is still in progress.
4. THE Paper_Store SHALL retain extracted data in memory for the duration of the server process.

### Requirement 7: Extraction Data Structure

**User Story:** As a developer, I want a well-defined data structure for extracted paper data, so that all components can interact with a consistent format.

#### Acceptance Criteria

1. THE Paper_Store SHALL organize each paper's data with the following top-level fields: paper_id (string), metadata (object or null), content (string or null), research_methods (string or null), and visual_assets (list or null).
2. THE Metadata field SHALL contain: title (string, maximum 500 characters), authors (list of strings, maximum 50 entries), institutions (list of strings, maximum 50 entries), journal (string or null, maximum 300 characters), and date (string in ISO 8601 date format "YYYY-MM-DD", or null if not identified).
3. THE Content field SHALL contain the full extracted text as a single string, or null if extraction has not yet completed.
4. THE Research_Methods field SHALL contain the methods section text as a string, or null if not identified or extraction has not yet completed.
5. THE Visual_Assets field SHALL contain a list of objects, each with page_number (integer, 1-indexed), width (integer, in pixels), height (integer, in pixels), and image_data (string, base64-encoded PNG).
6. IF extraction has not yet completed for a paper, THEN THE Paper_Store SHALL set metadata, content, research_methods, and visual_assets to null until their respective extraction steps finish.
