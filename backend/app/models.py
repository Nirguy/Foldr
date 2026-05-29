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
    type: str = "chart"  # "chart", "image", or "other"


class DatasetLink(BaseModel):
    """A dataset URL found in the paper."""

    url: str
    source: str  # Repository name (e.g., "Zenodo", "GitHub")
    context: str  # Surrounding text for context


class ImageEvaluation(BaseModel):
    """AI image detection result for a single visual asset."""

    page_number: Optional[int] = None
    type: str = "unknown"
    ai_score: float = 0.0
    ai_label: str = "unknown"  # "ai_generated", "natural", "error"
    ai_reasons: list[str] = Field(default_factory=list)


class MetadataEvaluation(BaseModel):
    """Predatory publisher check and MNCS score."""

    predatory_check: Optional[bool] = None  # True = on Beall's list
    predatory_journal: Optional[str] = None
    mncs_score: Optional[float] = None
    mncs_title: Optional[str] = None
    errors: list[str] = Field(default_factory=list)


class DatasetContent(BaseModel):
    """Tabular data fetched from a dataset URL (CSV/Excel)."""

    url: str  # Source URL
    filename: str  # Original filename
    columns: list[str] = Field(default_factory=list)  # Column headers
    rows: list[list] = Field(default_factory=list)  # Row data (list of lists)
    num_rows: int = 0  # Total rows in the original file
    truncated: bool = False  # Whether rows were truncated
    error: Optional[str] = None  # Error message if fetch/parse failed


class PaperEntry(BaseModel):
    """Full extraction result for a single paper."""

    paper_id: str
    status: str  # "extracting" | "complete"
    current_step: Optional[str] = None  # Current processing step description
    metadata: Optional[Metadata] = None
    content: Optional[str] = None
    skipped_pages: list[int] = Field(default_factory=list)
    research_methods: Optional[str] = None
    dataset_links: list[DatasetLink] = Field(default_factory=list)
    datasets: list[DatasetContent] = Field(default_factory=list)
    visual_assets: list[VisualAsset] = Field(default_factory=list)
    image_evaluation: list[ImageEvaluation] = Field(default_factory=list)
    metadata_evaluation: Optional[MetadataEvaluation] = None
    cherry_picking_evaluation: Optional[dict] = None
    lie_factor_evaluation: Optional[dict] = None
    graph_evaluation: Optional[dict] = None


class UploadResponse(BaseModel):
    """Response returned after a successful PDF upload."""

    paper_id: str


class ErrorResponse(BaseModel):
    """Response returned when an error occurs."""

    error: str
