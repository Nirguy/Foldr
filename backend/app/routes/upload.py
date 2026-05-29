import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, UploadFile
from fastapi.responses import JSONResponse

from app.extractor import run_extraction
from app.store import create_entry, update_entry

router = APIRouter()

MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB (effectively no limit for hackathon)
PDF_MAGIC_BYTES = b"%PDF"
DATASET_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls", ".xlsm"}


@router.post("/upload", status_code=202)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    dataset: Optional[UploadFile] = File(None),
):
    """Accept a PDF file upload with optional dataset, validate, and dispatch extraction."""

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

    # Validate: file size
    if len(contents) > MAX_FILE_SIZE:
        return JSONResponse(
            status_code=400,
            content={"error": "File exceeds the 200 MB size limit"},
        )

    # Generate UUID v4 and store entry
    paper_id = str(uuid.uuid4())
    create_entry(paper_id, contents)

    # Handle optional dataset file
    if dataset and dataset.filename:
        try:
            dataset_bytes = await dataset.read()
            if len(dataset_bytes) > 0:
                update_entry(
                    paper_id,
                    dataset_file={
                        "filename": dataset.filename,
                        "bytes": dataset_bytes,
                    },
                )
        except Exception:
            pass  # Don't fail the upload if dataset read fails

    # Enqueue extraction as a background task
    background_tasks.add_task(run_extraction, paper_id)

    return {"paper_id": paper_id}
