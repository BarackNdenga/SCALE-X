"""HTTP API for the SCALE-X Data Fitness Engine V0.1."""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from analyzer import MAX_BYTES, MAX_ROWS, analyse_dataset, parse_dataset

app = FastAPI(
    title="SCALE-X Data Fitness Engine",
    version="0.1.0",
    description="Analyse légère de datasets et calcul explicable du Data Fitness Score.",
)


def _allowed_origins() -> list[str]:
    configured = os.getenv("FRONTEND_ORIGIN", "*").strip()
    if configured == "*":
        return ["*"]
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "name": "SCALE-X Data Fitness Engine",
        "version": "0.1.0",
        "status": "online",
        "docs": "/docs",
        "endpoint": "POST /analyze",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "scalex-data-fitness-engine"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)) -> dict[str, Any]:
    """Analyse un fichier CSV, JSON, JSONL ou TXT en mémoire."""
    filename = file.filename or "dataset"
    extension = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    allowed_extensions = {"csv", "json", "jsonl", "ndjson", "txt"}
    if extension not in allowed_extensions:
        raise HTTPException(status_code=415, detail="Format non supporté. Utilisez CSV, JSON, JSONL ou TXT.")

    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"Fichier trop volumineux. Limite : {MAX_BYTES // (1024 * 1024)} MB.")

    try:
        parsed = parse_dataset(filename, data)
        report = analyse_dataset(parsed)
        report["dataset"]["filename"] = filename
        report["dataset"]["max_rows"] = MAX_ROWS
        return report
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover — garde-fou API pour la V0.1
        raise HTTPException(status_code=500, detail="L'analyse a échoué. Vérifiez la structure du fichier.") from exc
