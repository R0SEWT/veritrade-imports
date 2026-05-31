"""Validación y reparación de la salida del LLM.

- Parseo robusto del JSON (repara cortes/comas colgantes).
- Normalización de enums vía sinónimos del vocabulario.
- Fuzzy-match del modelo contra los modelos canónicos de la marca.
- Genera columnas derivadas + flags; nunca descarta en silencio.
"""
from __future__ import annotations

import json
import re

from .vocab import Vocab, norm_key

try:
    from rapidfuzz import fuzz, process

    def _best(query: str, choices: list[str]):
        if not choices:
            return None, 0.0
        m = process.extractOne(query, choices, scorer=fuzz.WRatio)
        return (m[0], float(m[1])) if m else (None, 0.0)
except ImportError:  # fallback stdlib
    import difflib

    def _best(query: str, choices: list[str]):
        if not choices:
            return None, 0.0
        m = difflib.get_close_matches(query, choices, n=1, cutoff=0.0)
        if not m:
            return None, 0.0
        score = difflib.SequenceMatcher(None, query, m[0]).ratio() * 100
        return m[0], float(score)


MODELO_OK = 90.0
MODELO_LOW = 75.0


def parse_json_lenient(text: str) -> dict | None:
    """Intenta json.loads; si falla, recorta al objeto {...} y limpia comas colgantes."""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    chunk = text[start:end + 1]
    chunk = re.sub(r",\s*([}\]])", r"\1", chunk)  # comas colgantes
    try:
        return json.loads(chunk)
    except json.JSONDecodeError:
        return None


def items_by_index(parsed: dict | None) -> dict[int, dict]:
    """Extrae {i: item} de una respuesta parseada. Tolera lista directa."""
    if not parsed:
        return {}
    items = parsed.get("items") if isinstance(parsed, dict) else parsed
    out: dict[int, dict] = {}
    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict) and "i" in it:
                try:
                    out[int(it["i"])] = it
                except (TypeError, ValueError):
                    continue
    return out


def normalize_record(item: dict, v: Vocab) -> dict:
    """Convierte un item crudo del LLM en el registro normalizado + flags."""
    rec: dict = {}

    # --- marca ---
    marca_raw = (item.get("marca") or None)
    marca_raw = marca_raw.strip() if isinstance(marca_raw, str) and marca_raw.strip() else None
    rec["marca_raw_llm"] = marca_raw
    if marca_raw:
        canon = v.marca_canonica(marca_raw)
        if canon:
            # coincide (normalizado) con una marca canónica del vocabulario
            rec["marca_norm"], rec["marca_in_vocab"] = canon, True
            rec["marca_sugerencia"] = None
        else:
            # marca NUEVA (fuera del ejemplo): se conserva tal cual, no se fuerza.
            # Se guarda una sugerencia de la más parecida (>=90) solo informativa.
            cand, score = _best(norm_key(marca_raw), [norm_key(m) for m in v.marcas])
            back = next((m for m in v.marcas if norm_key(m) == cand), None) if cand else None
            rec["marca_norm"] = marca_raw.upper()
            rec["marca_in_vocab"] = False
            rec["marca_sugerencia"] = back if (back and score >= MODELO_OK) else None
    else:
        rec["marca_norm"], rec["marca_in_vocab"], rec["marca_sugerencia"] = None, False, None

    # --- modelo (fuzzy contra modelos de la marca canónica) ---
    modelo_raw = item.get("modelo_codigo")
    modelo_raw = modelo_raw.strip() if isinstance(modelo_raw, str) and modelo_raw.strip() else None
    rec["modelo_raw_llm"] = modelo_raw
    marca_for_models = rec["marca_norm"] if rec["marca_in_vocab"] else None
    # 1) alias de modelo explícito (curado por SME) tiene prioridad
    alias_modelo = v.modelo_alias(marca_for_models, modelo_raw) if (marca_for_models and modelo_raw) else None
    choices = v.modelos_por_marca.get(marca_for_models, []) if marca_for_models else []
    if alias_modelo:
        rec["modelo_match"] = alias_modelo
        rec["modelo_score"] = 100.0
        rec["modelo_flag"] = "ok"
    elif modelo_raw and choices:
        match, score = _best(modelo_raw, choices)
        rec["modelo_match"] = match
        rec["modelo_score"] = round(score, 1)
        rec["modelo_flag"] = "ok" if score >= MODELO_OK else ("low" if score >= MODELO_LOW else "nomatch")
    elif modelo_raw:
        rec["modelo_match"] = None
        rec["modelo_score"] = None
        rec["modelo_flag"] = "nomatch"  # marca fuera de vocab o sin candidatos
    else:
        rec["modelo_match"] = None
        rec["modelo_score"] = None
        rec["modelo_flag"] = "sin_dato"

    # --- enums ---
    for campo in ("traccion", "combustible", "clasificacion", "caja"):
        raw = item.get(campo)
        norm = v.enum_norm(campo, raw if isinstance(raw, str) else None)
        rec[f"{campo}_norm"] = norm
        rec[f"{campo}_valido"] = norm is not None if (raw not in (None, "")) else True

    return rec


def empty_record() -> dict:
    """Registro vacío para filas sin respuesta del LLM."""
    rec = {
        "marca_raw_llm": None, "marca_norm": None, "marca_in_vocab": False,
        "marca_sugerencia": None,
        "modelo_raw_llm": None, "modelo_match": None, "modelo_score": None,
        "modelo_flag": "sin_respuesta",
    }
    for campo in ("traccion", "combustible", "clasificacion", "caja"):
        rec[f"{campo}_norm"] = None
        rec[f"{campo}_valido"] = True
    return rec
