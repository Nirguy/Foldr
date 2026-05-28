# Pydantic data models for paper extraction

from pydantic import BaseModel, Field
from typing import Optional


class Metadata(BaseModel):
    """Structured metadata extracted from an academic paper."""

    title: str = Field(max_length=500)
    authors: list[str] = Field(default_factory=list, max_length=50)
    institutions: list[str] = Field(default_factory=list, max_length=50)
    journal: Optional[str] = Field(default=None, max_length=300)
    date: Optional[str] = None  # ISO 8601 YYYY-MM-DD or None


class VisualAsset(BaseModel):
    """A rendered page image from the PDF."""

    page_number: int  # 1-indexed
    width: int  # pixels
    height: int  # pixels
    image_data: str  # base64-encoded PNG


class DatasetLink(BaseModel):
    """A dataset URL found in the paper."""

    url: str
    source: str  # Repository name (e.g., "Zenodo", "GitHub")
    context: str  # Surrounding text for context


class PaperEntry(BaseModel):
    """Full extraction result for a single paper."""

    paper_id: str
    status: str  # "extracting" | "complete"
    metadata: Optional[Metadata] = None
    content: Optional[str] = None
    skipped_pages: list[int] = Field(default_factory=list)
    research_methods: Optional[str] = None
    dataset_links: list[DatasetLink] = Field(default_factory=list)
    visual_assets: list[VisualAsset] = Field(default_factory=list)


class UploadResponse(BaseModel):
    """Response returned after a successful PDF upload."""

    paper_id: str


class ErrorResponse(BaseModel):
    """Response returned when an error occurs."""

    error: str
