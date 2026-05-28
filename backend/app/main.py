from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import papers, upload

app = FastAPI(title="Foldr API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api")
app.include_router(papers.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
