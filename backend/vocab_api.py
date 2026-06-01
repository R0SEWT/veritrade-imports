"""Rutas /vocab/* para gestionar el vocabulario sin tocar archivos manualmente."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

EXTRA_PATH = Path("data/vocab_extra.json")
VOCAB_PATH = Path("data/ejemplo.xlsx")

router = APIRouter(prefix="/vocab", tags=["vocab"])


def _load_extra() -> dict:
    if not EXTRA_PATH.exists():
        return {"aliases": {}, "marcas": {}, "model_aliases": {}}
    return json.loads(EXTRA_PATH.read_text(encoding="utf-8"))


def _save_extra(data: dict) -> None:
    EXTRA_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


@router.get("/brands")
def get_brands() -> dict:
    """Devuelve marcas canónicas de ejemplo.xlsx + marcas extra de vocab_extra.json."""
    import sys
    from pathlib import Path as _Path
    PROJECT_ROOT = _Path(__file__).resolve().parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from scripts.llm import vocab as vocab_mod

    v = vocab_mod.load(VOCAB_PATH)
    extra = _load_extra()
    return {
        "brands": v.marcas,
        "aliases": extra.get("aliases", {}),
        "model_aliases": extra.get("model_aliases", {}),
        "extra_brands": list(extra.get("marcas", {}).keys()),
    }


class BrandAliasRequest(BaseModel):
    alias: str
    canonical: str


class ModelAliasRequest(BaseModel):
    brand: str
    raw_model: str
    canonical_model: str


@router.post("/aliases")
def add_brand_alias(req: BrandAliasRequest) -> dict:
    """Agrega un alias de marca (variante cruda → marca canónica)."""
    extra = _load_extra()
    aliases = extra.setdefault("aliases", {})
    if req.alias in aliases:
        raise HTTPException(400, f"Alias '{req.alias}' ya existe")
    aliases[req.alias] = req.canonical
    _save_extra(extra)
    return {"ok": True, "alias": req.alias, "canonical": req.canonical}


@router.delete("/aliases/{alias}")
def delete_brand_alias(alias: str) -> dict:
    extra = _load_extra()
    aliases = extra.get("aliases", {})
    if alias not in aliases:
        raise HTTPException(404, f"Alias '{alias}' no encontrado")
    del aliases[alias]
    _save_extra(extra)
    return {"ok": True}


@router.post("/model-aliases")
def add_model_alias(req: ModelAliasRequest) -> dict:
    """Agrega un alias de modelo para una marca específica."""
    extra = _load_extra()
    model_aliases = extra.setdefault("model_aliases", {})
    brand_map = model_aliases.setdefault(req.brand, {})
    brand_map[req.raw_model] = req.canonical_model
    _save_extra(extra)
    return {"ok": True, "brand": req.brand, "raw": req.raw_model, "canonical": req.canonical_model}


@router.delete("/model-aliases/{brand}/{raw_model}")
def delete_model_alias(brand: str, raw_model: str) -> dict:
    extra = _load_extra()
    brand_map = extra.get("model_aliases", {}).get(brand, {})
    if raw_model not in brand_map:
        raise HTTPException(404, "Alias de modelo no encontrado")
    del brand_map[raw_model]
    _save_extra(extra)
    return {"ok": True}
