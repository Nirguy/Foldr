import uuid

from fastapi import APIRouter, BackgroundTasks, File, UploadFile
from fastapi.responses import JSONResponse

from app.extractor import run_extraction
from app.store import create_entry

router = APIRouter()

MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB (effectively no limit for hackathon)
PDF_MAGIC_BYTES = b"%PDF"


@router.post("/upload", status_code=202)
async def upload_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Accept a PDF file upload, validate it, and dispatch extraction as a background task."""

    contents = await file.read()

    # Validate: file is present and non-empty
    if len(contents) == 0:
        return JSONResponse(
            status_code=400,
            content={"error": "A non-empty PDF file is required"},
        )

    # Validate: file starts with %PDF magic bytes
    if not contents.startswith(PDF_MAGIC_BYTES):
        return JSONResponse(
            status_code=400,
            content={"error": "Only PDF files are supported"},
        )

    # Validate: file size ≤ 20 MB
    if len(contents) > MAX_FILE_SIZE:
        return JSONResponse(
            status_code=400,
            content={"error": "File exceeds the 20 MB size limit"},
        )

    # Generate UUID v4 and store entry
    paper_id = str(uuid.uuid4())
    create_entry(paper_id, contents)

    # Enqueue extraction as a background task
    background_tasks.add_task(run_extraction, paper_id)

    return {"paper_id": paper_id}
