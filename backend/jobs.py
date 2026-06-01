"""Job store en SQLite + lanzador del pipeline en background thread."""
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

JOBS_DIR = Path("jobs")
DB_PATH = Path("backend.db")

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',
    input_filename TEXT,
    mode TEXT NOT NULL DEFAULT 'both',
    progress_pct REAL NOT NULL DEFAULT 0,
    rows_total INTEGER,
    rows_processed INTEGER,
    cost_usd REAL,
    error TEXT,
    created_at TEXT NOT NULL
)
"""


@dataclass
class JobState:
    id: str
    status: str
    input_filename: str
    mode: str
    progress_pct: float
    rows_total: Optional[int]
    rows_processed: Optional[int]
    cost_usd: Optional[float]
    error: Optional[str]
    created_at: str


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init_db() -> None:
    JOBS_DIR.mkdir(exist_ok=True)
    with _conn() as c:
        c.execute(_CREATE_SQL)


def create_job(filename: str, mode: str) -> str:
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        c.execute(
            "INSERT INTO jobs (id, status, input_filename, mode, created_at) VALUES (?,?,?,?,?)",
            (job_id, "pending", filename, mode, now),
        )
    return job_id


def update_job(job_id: str, **fields) -> None:
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [job_id]
    with _conn() as c:
        c.execute(f"UPDATE jobs SET {sets} WHERE id=?", vals)


def get_job(job_id: str) -> Optional[JobState]:
    with _conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        return None
    return JobState(**dict(row))


def list_jobs() -> list[JobState]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    return [JobState(**dict(r)) for r in rows]


def run_pipeline(job_id: str, api_key: str) -> None:
    """Corre en un thread de background. Actualiza el job en SQLite a medida que avanza."""
    from . import pipeline  # importación diferida para evitar ciclos

    job = get_job(job_id)
    if job is None:
        return

    job_dir = JOBS_DIR / job_id
    input_path = job_dir / "input.xlsx"
    v1_path = job_dir / "estructurado.xlsx"
    norm_path = job_dir / "normalizado.xlsx"

    try:
        # ── Phase 1 ──────────────────────────────────────────────
        update_job(job_id, status="running_phase1", progress_pct=5)
        rows_total = pipeline.run_phase1(input_path, v1_path)
        update_job(job_id, rows_total=rows_total)

        if job.mode == "phase1":
            update_job(job_id, status="done", progress_pct=100)
            return

        # ── Phase 2 ──────────────────────────────────────────────
        update_job(job_id, status="running_phase2", progress_pct=30)

        def on_progress(done: int, total: int) -> None:
            pct = 30 + int(done / total * 65) if total > 0 else 30
            update_job(job_id, progress_pct=pct, rows_processed=done)

        cost = pipeline.run_phase2(input_path, v1_path, norm_path, api_key, on_progress)
        update_job(job_id, status="done", progress_pct=100, cost_usd=cost)

    except Exception as exc:
        update_job(job_id, status="error", error=str(exc))
