# Papers route - GET /api/papers/{paper_id} retrieval endpoint

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models import PaperEntry
from app.store import get_entry

router = APIRouter()


@router.get("/papers/{paper_id}")
def get_paper(paper_id: str):
    """Retrieve extraction results for a given paper ID."""
    entry = get_entry(paper_id)

    if entry is None:
        return JSONResponse(status_code=404, content={"error": "Paper not found"})

    # Sanitize metadata: ensure list fields are never None (Pydantic expects lists)
    metadata = entry.get("metadata")
    if metadata is not None:
        metadata = {
            "title": metadata.get("title") or "",
            "authors": metadata.get("authors") or [],
            "institutions": metadata.get("institutions") or [],
            "journal": metadata.get("journal"),
            "date": metadata.get("date"),
        }

    # Build response from store entry, excluding raw_bytes
    paper = PaperEntry(
        paper_id=entry["paper_id"],
        status=entry["status"],
        metadata=metadata,
        content=entry.get("content"),
        skipped_pages=entry.get("skipped_pages", []),
        research_methods=entry.get("research_methods"),
        dataset_links=entry.get("dataset_links", []),
        visual_assets=entry.get("visual_assets", []),
    )

    return JSONResponse(status_code=200, content=paper.model_dump())
