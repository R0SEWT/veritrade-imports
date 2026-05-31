"""Construcción del prompt para DeepSeek (JSON mode) y forma del JSON esperado.

El prefijo (system) es ESTABLE entre requests (marcas + enums + few-shot) para
maximizar el prompt-cache de DeepSeek; solo varían los items del mensaje user.
"""
from __future__ import annotations

import json

from .vocab import Vocab

OUTPUT_KEYS = ["marca", "modelo_codigo", "traccion", "combustible", "clasificacion", "caja"]


def build_system_prompt(v: Vocab) -> str:
    marcas = ", ".join(v.marcas)
    return f"""Eres un normalizador de descripciones aduaneras de camiones (Perú, partida 8704229000).
Recibes un JSON con una lista `items`, cada uno con `i` (índice) y `desc` (texto de la descripción comercial).
Para CADA item, extrae y normaliza EXACTAMENTE estos 6 campos y responde SOLO con JSON válido.

Campos y valores permitidos:
- marca: una de esta lista EXACTA de marcas (cópiala tal cual). Si la marca del texto NO está en la lista, usa null. NO inventes.
  Lista: {marcas}
- modelo_codigo: el código/modelo del vehículo tal como aparece en el texto (string corto, p.ej. "DF-1718", "FVR34", "1828"). null si no se puede determinar.
- traccion: una de [4x2, 4x4, 6x4, 6x8]. null si no aparece.
- combustible: una de [Diesel, GNV, GLP, Gasolina]. null si no aparece.
- clasificacion: una de [N1, N2, N3]. null si no aparece.
- caja: una de [Mecanico, Automatico, AMT, MT]. null si no aparece.

Reglas:
- Responde con un objeto JSON: {{"items": [{{"i": <int>, "marca": ..., "modelo_codigo": ..., "traccion": ..., "combustible": ..., "clasificacion": ..., "caja": ...}}, ...]}}
- Devuelve un item por cada `i` recibido, con el mismo `i`.
- Usa null (no cadena vacía) cuando un campo no se pueda determinar.
- No agregues texto fuera del JSON.

Ejemplo de entrada:
{{"items": [{{"i": 0, "desc": "N3  MARCA:DONGFENG, MODELO:DF-1718, AÑO:2023, FR:4X2, CO:DIESEL(PETROLEO), TT:MEC"}}]}}
Ejemplo de salida:
{{"items": [{{"i": 0, "marca": "DONGFENG", "modelo_codigo": "DF-1718", "traccion": "4x2", "combustible": "Diesel", "clasificacion": "N3", "caja": "Mecanico"}}]}}"""


def build_user_message(batch: list[tuple[int, str]]) -> str:
    """batch: lista de (i, desc). Devuelve el JSON del mensaje user."""
    items = [{"i": i, "desc": desc} for i, desc in batch]
    return json.dumps({"items": items}, ensure_ascii=False)
