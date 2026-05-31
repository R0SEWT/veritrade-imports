"""Muestreo estratificado de ~300 filas para evaluar la fase B.

Estratos (mide el 'lift' del LLM donde el determinístico falla):
  - sin_modelo  ~40%  (modelo ausente en v1)
  - lista_comas ~20%  (formato 'N3,FUSO,FJ,...' sin 'MARCA:')
  - limpia      ~25%  (modelo presente -> medir acuerdo / falsos cambios)
  - marca_rara  ~15%  (marca fuera del vocabulario controlado)
"""
from __future__ import annotations

import re

import pandas as pd

from .vocab import Vocab

SEED = 42
COMMA_LIST_RE = re.compile(r"^\s*N\d\s*,", re.IGNORECASE)


def assign_estrato(df: pd.DataFrame, vocab: Vocab) -> pd.Series:
    in_vocab = df["marca"].map(lambda m: vocab.marca_canonica(m) is not None if isinstance(m, str) else False)
    comma = df["_desc"].map(lambda s: bool(COMMA_LIST_RE.match(str(s))) if pd.notna(s) else False)
    no_modelo = df["modelo"].isna()

    est = pd.Series(index=df.index, dtype="object")
    est[:] = "limpia"
    est[comma] = "lista_comas"
    est[no_modelo] = "sin_modelo"
    est[~in_vocab] = "marca_rara"  # prioridad alta: robustez fuera de vocab
    return est


def sample(df: pd.DataFrame, vocab: Vocab, n: int = 300) -> pd.DataFrame:
    df = df.copy()
    df["estrato"] = assign_estrato(df, vocab)
    cuotas = {"sin_modelo": 0.40, "lista_comas": 0.20, "limpia": 0.25, "marca_rara": 0.15}
    partes = []
    for estrato, frac in cuotas.items():
        pool = df[df["estrato"] == estrato]
        k = min(len(pool), round(n * frac))
        if k:
            partes.append(pool.sample(n=k, random_state=SEED))
    out = pd.concat(partes).drop_duplicates(subset=["row_key"])
    # rellenar hasta n si quedó corto
    if len(out) < n:
        resto = df.drop(out.index)
        extra = resto.sample(n=min(len(resto), n - len(out)), random_state=SEED)
        out = pd.concat([out, extra])
    return out.reset_index(drop=True)
