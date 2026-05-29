# Upload URL route - POST /api/upload-url
# Fetches a PDF from a given URL and processes it

import uuid

import requests
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.extractor import run_extraction
from app.store import create_entry

router = APIRouter()

TIMEOUT = 60  # seconds
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB
PDF_MAGIC_BYTES = b"%PDF"


class UrlRequest(BaseModel):
    url: str


@router.post("/upload-url", status_code=202)
async def upload_from_url(body: UrlRequest, background_tasks: BackgroundTasks):
    """Fetch a PDF from a URL, validate it, and dispatch extraction."""
    url = body.url.strip()

    if not url:
        return JSONResponse(
            status_code=400,
            content={"error": "URL is required"},
        )

    # Fetch the PDF
    try:
        resp = requests.get(url, timeout=TIMEOUT, allow_redirects=True, stream=True)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        return JSONResponse(
            status_code=400,
            content={"error": "Request timed out fetching the URL"},
        )
    except requests.exceptions.RequestException as e:
        return JSONResponse(
            status_code=400,
            content={"error": f"Failed to fetch URL: {str(e)[:200]}"},
        )

    contents = resp.content

    # Validate: non-empty
    if len(contents) == 0:
        return JSONResponse(
            status_code=400,
            content={"error": "URL returned empty content"},
        )

    # Validate: PDF magic bytes
    if not contents.startswith(PDF_MAGIC_BYTES):
        return JSONResponse(
            status_code=400,
            content={"error": "URL does not point to a valid PDF file"},
        )

    # Validate: size
    if len(contents) > MAX_FILE_SIZE:
        return JSONResponse(
            status_code=400,
            content={"error": "PDF exceeds the 200 MB size limit"},
        )

    # Generate UUID and store
    paper_id = str(uuid.uuid4())
    create_entry(paper_id, contents)

    # Enqueue extraction
    background_tasks.add_task(run_extraction, paper_id)

    return {"paper_id": paper_id}
