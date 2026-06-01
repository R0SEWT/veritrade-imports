"""FastAPI app — Web service para el pipeline Veritrade Imports.

Arranque (desde raíz del proyecto):
    uvicorn backend.main:app --reload --port 8000
"""
from __future__ import annotations

import os
from pathlib import Path

# Asegurar que uvicorn corre desde la raíz del proyecto
os.chdir(Path(__file__).resolve().parent.parent)

import json
from typing import Optional

import pandas as pd
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .jobs import (
    JobState,
    create_job,
    get_job,
    init_db,
    list_jobs,
    run_pipeline,
)
from .vocab_api import router as vocab_router

JOBS_DIR = Path("jobs")
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

app = FastAPI(title="Veritrade Imports — Pipeline Web")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vocab_router)


@app.on_event("startup")
async def startup():
    init_db()


# ── Jobs ─────────────────────────────────────────────────────────────────────


class JobResponse(BaseModel):
    id: str
    status: str
    input_filename: Optional[str]
    mode: str
    progress_pct: float
    rows_total: Optional[int]
    rows_processed: Optional[int]
    cost_usd: Optional[float]
    error: Optional[str]
    created_at: str


def _job_resp(j: JobState) -> JobResponse:
    return JobResponse(**j.__dict__)


@app.post("/jobs", response_model=JobResponse)
async def create_job_route(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    api_key: str = Form(...),
    mode: str = Form("both"),
):
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(400, "Solo se aceptan archivos .xlsx")
    if mode not in ("phase1", "both"):
        raise HTTPException(400, "mode debe ser 'phase1' o 'both'")

    job_id = create_job(file.filename, mode)
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    input_path = job_dir / "input.xlsx"
    input_path.write_bytes(await file.read())

    background_tasks.add_task(run_pipeline, job_id, api_key)

    job = get_job(job_id)
    return _job_resp(job)


@app.get("/jobs", response_model=list[JobResponse])
def list_jobs_route():
    return [_job_resp(j) for j in list_jobs()]


@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job_route(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job no encontrado")
    return _job_resp(job)


@app.get("/jobs/{job_id}/data")
def get_job_data(job_id: str, page: int = 1, per_page: int = 100, search: str = ""):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job no encontrado")
    if job.status not in ("done",):
        raise HTTPException(409, "Job aún no terminado")

    job_dir = JOBS_DIR / job_id
    xlsx = job_dir / "normalizado.xlsx" if job.mode == "both" else job_dir / "estructurado.xlsx"
    if not xlsx.exists():
        raise HTTPException(404, "Archivo de resultado no encontrado")

    sheet = "normalizado_llm" if job.mode == "both" else "estructurado"
    df = pd.read_excel(xlsx, sheet_name=sheet)

    if search:
        mask = df.apply(
            lambda col: col.astype(str).str.contains(search, case=False, na=False)
        ).any(axis=1)
        df = df[mask]

    total = len(df)
    start = (page - 1) * per_page
    chunk = df.iloc[start : start + per_page]

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "rows": json.loads(chunk.to_json(orient="records", force_ascii=False, date_format="iso")),
    }


@app.get("/jobs/{job_id}/summary")
def get_job_summary(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job no encontrado")
    if job.status not in ("done",):
        raise HTTPException(409, "Job aún no terminado")

    job_dir = JOBS_DIR / job_id
    xlsx = job_dir / "normalizado.xlsx" if job.mode == "both" else job_dir / "estructurado.xlsx"
    if not xlsx.exists():
        raise HTTPException(404, "Archivo de resultado no encontrado")

    sheet = "normalizado_llm" if job.mode == "both" else "estructurado"
    df = pd.read_excel(xlsx, sheet_name=sheet)
    total = len(df)

    summary: dict = {"total_rows": total, "cost_usd": job.cost_usd}

    # Fill rates de campos clave
    key_fields = ["marca", "modelo", "vin", "chasis", "cilindrada_cc", "traccion"]
    fill = {}
    for col in key_fields:
        if col in df.columns:
            fill[col] = round(df[col].notna().mean() * 100, 1)
    summary["fill_rates"] = fill

    # Distribuciones (pandas 2.x: value_counts().reset_index() ya da [col, "count"])
    if "marca" in df.columns:
        top_marcas = df["marca"].value_counts().head(15).reset_index()
        summary["marca_dist"] = top_marcas.to_dict("records")

    traccion_col = "traccion_norm" if "traccion_norm" in df.columns else "traccion"
    if traccion_col in df.columns:
        top_tr = df[traccion_col].value_counts().reset_index()
        summary["traccion_dist"] = top_tr.to_dict("records")

    # Serie temporal (por mes)
    if "fecha" in df.columns:
        df["_month"] = pd.to_datetime(df["fecha"], errors="coerce").dt.to_period("M").astype(str)
        monthly = (
            df.groupby("_month").size().reset_index(name="count")
            .rename(columns={"_month": "month"})
            .sort_values("month")
        )
        summary["monthly"] = monthly.to_dict("records")

    return summary


@app.get("/jobs/{job_id}/download/{phase}")
def download_job_file(job_id: str, phase: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job no encontrado")
    if job.status != "done":
        raise HTTPException(409, "Job aún no terminado")

    job_dir = JOBS_DIR / job_id
    if phase == "phase1":
        path = job_dir / "estructurado.xlsx"
        fname = "estructurado.xlsx"
    elif phase == "phase2":
        path = job_dir / "normalizado.xlsx"
        fname = "normalizado.xlsx"
    else:
        raise HTTPException(400, "phase debe ser 'phase1' o 'phase2'")

    if not path.exists():
        raise HTTPException(404, "Archivo no disponible")
    return FileResponse(path, filename=fname, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ── Static files (frontend build en producción) ───────────────────────────────

if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="static")
