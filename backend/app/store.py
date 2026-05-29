# Paper Store - in-memory storage for extracted paper data

from threading import Lock
from typing import Any

_store: dict[str, dict[str, Any]] = {}
_lock = Lock()


def create_entry(paper_id: str, raw_bytes: bytes) -> None:
    """Store raw PDF bytes with initial 'extracting' status and null extraction fields."""
    with _lock:
        _store[paper_id] = {
            "paper_id": paper_id,
            "status": "extracting",
            "current_step": "Starting extraction...",
            "raw_bytes": raw_bytes,
            "metadata": None,
            "content": None,
            "skipped_pages": [],
            "research_methods": None,
            "dataset_links": [],
            "datasets": [],
            "visual_assets": [],
            "image_evaluation": [],
            "metadata_evaluation": {},
            "cherry_picking_evaluation": {},
            "lie_factor_evaluation": {},
            "graph_evaluation": {},
        }


def get_entry(paper_id: str) -> dict[str, Any] | None:
    """Return the entry for a given paper_id, or None if not found."""
    with _lock:
        entry = _store.get(paper_id)
        if entry is None:
            return None
        return dict(entry)


def update_entry(paper_id: str, **fields: Any) -> None:
    """Update specified fields on an existing entry."""
    with _lock:
        if paper_id in _store:
            _store[paper_id].update(fields)
