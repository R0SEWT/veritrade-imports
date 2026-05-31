"""Reporte de evaluación: LLM normalizado vs parser determinístico (v1)."""
from __future__ import annotations

import pandas as pd

from .client import Stats

# Precios deepseek-v4-flash (USD por 1M tokens), recalcular si cambian.
PRICE_IN_MISS = 0.14
PRICE_IN_HIT = 0.0028
PRICE_OUT = 0.28


def build(df: pd.DataFrame, stats: Stats) -> pd.DataFrame:
    """df ya tiene columnas v1 (marca, modelo) + LLM (marca_norm, modelo_match, modelo_flag, *_norm)."""
    filas = []

    def pct(mask):
        return round(100 * mask.mean(), 1) if len(df) else 0.0

    filas.append(("filas_muestra", len(df)))

    # Fill-rate de modelo: v1 vs LLM (ok exacto + alias curado + low)
    resueltos = ["ok", "alias", "low"]
    filas.append(("modelo_fill_v1_%", pct(df["modelo"].notna())))
    filas.append(("modelo_fill_llm_%", pct(df["modelo_flag"].isin(resueltos))))

    # Lift en el estrato sin_modelo
    if "estrato" in df:
        sm = df[df["estrato"] == "sin_modelo"]
        if len(sm):
            filas.append(("lift_modelo_en_sin_modelo_%",
                          round(100 * sm["modelo_flag"].isin(resueltos).mean(), 1)))

    # Acuerdo de marca (donde v1 tiene marca y LLM la dejó in_vocab)
    comp = df[df["marca"].notna() & df["marca_norm"].notna()]
    if len(comp):
        ag = (comp["marca"].str.upper().str.strip() == comp["marca_norm"].str.upper().str.strip())
        filas.append(("acuerdo_marca_%", round(100 * ag.mean(), 1)))
    filas.append(("marca_fuera_vocab_%", pct(~df["marca_in_vocab"])))

    # Distribución de flags de modelo
    for flag, c in df["modelo_flag"].value_counts().items():
        filas.append((f"modelo_flag::{flag}", int(c)))

    # Validez de enums
    for campo in ("traccion", "combustible", "clasificacion", "caja"):
        filas.append((f"{campo}_fill_%", pct(df[f"{campo}_norm"].notna())))

    # Costo / tokens
    miss = max(stats.prompt_tokens - stats.cached_tokens, 0)
    costo = (miss * PRICE_IN_MISS + stats.cached_tokens * PRICE_IN_HIT
             + stats.completion_tokens * PRICE_OUT) / 1_000_000
    filas += [
        ("requests", stats.requests),
        ("errores_batch", stats.errors),
        ("prompt_tokens", stats.prompt_tokens),
        ("cached_tokens", stats.cached_tokens),
        ("completion_tokens", stats.completion_tokens),
        ("costo_estimado_usd", round(costo, 4)),
    ]
    return pd.DataFrame(filas, columns=["metrica", "valor"])
