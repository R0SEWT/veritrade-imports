"""Carga del vocabulario controlado desde ejemplo.xlsx.

Expone marcas canónicas (188), modelos por marca (939), los enums cerrados
(tracción/combustible/clasificación/caja) y tablas de sinónimos para
normalizar valores crudos a la forma canónica.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl

DEFAULT_PATH = "ejemplo.xlsx"
EXTRA_PATH = "data/vocab_extra.json"

# Sinónimos -> valor canónico (claves en MAYÚSCULAS, ya normalizadas con norm_key)
COMBUSTIBLE_SYN = {
    "DIESEL": "Diesel", "PETROLEO": "Diesel", "DIESELPETROLEO": "Diesel",
    "BIODIESEL": "Diesel", "PETROLEODIESEL": "Diesel",
    "GASOLINA": "Gasolina", "NAFTA": "Gasolina",
    "GNV": "GNV", "GASNATURAL": "GNV", "GAS": "GNV",
    "GLP": "GLP",
}
CAJA_SYN = {
    "MECANICO": "Mecanico", "MECANICA": "Mecanico", "MANUAL": "Mecanico",
    "MEC": "Mecanico", "MT": "MT", "M/T": "MT",
    "AUTOMATICO": "Automatico", "AUTOMATICA": "Automatico", "AUTO": "Automatico",
    "AT": "Automatico", "A/T": "Automatico",
    "AMT": "AMT",
}
TRACCION_SYN = {
    "4X2": "4x2", "4X4": "4x4", "6X4": "6x4", "6X8": "6x8",
    "6X2": "6x2", "8X4": "8x4",  # vistos en data; quedan como "fuera de vocab" si no están en enum
}
CLASIFICACION_SYN = {"N1": "N1", "N2": "N2", "N3": "N3"}


def norm_key(s: str) -> str:
    """Normaliza para comparar: mayúsculas, sin acentos triviales ni separadores."""
    s = (s or "").strip().upper()
    s = s.replace("Ó", "O").replace("Í", "I").replace("Á", "A").replace("É", "E").replace("Ú", "U")
    return re.sub(r"[\s\-_/().]", "", s)


@dataclass
class Vocab:
    marcas: list[str]                      # 188 canónicas (orden de aparición)
    modelos_por_marca: dict[str, list[str]]  # marca canónica -> [códigos]
    traccion: list[str]
    combustible: list[str]
    clasificacion: list[str]
    caja: list[str]
    _marca_idx: dict[str, str] = field(default_factory=dict)  # norm_key -> marca canónica
    _alias_idx: dict[str, str] = field(default_factory=dict)   # norm_key(alias) -> marca canónica
    # marca canónica -> {norm_key(modelo_raw) -> modelo canónico}
    _model_alias: dict[str, dict[str, str]] = field(default_factory=dict)

    def marca_canonica(self, raw: str) -> str | None:
        """Marca canónica si raw coincide (normalizado) con una marca o un alias; si no None."""
        k = norm_key(raw)
        return self._marca_idx.get(k) or self._alias_idx.get(k)

    def modelo_alias(self, marca_canon: str, raw: str) -> str | None:
        """Modelo canónico si hay alias de modelo (match normalizado exacto) para esa marca."""
        return self._model_alias.get(marca_canon, {}).get(norm_key(raw))

    def enum_norm(self, campo: str, raw: str) -> str | None:
        """Normaliza un valor de enum vía sinónimos. None si no mapea a un valor permitido."""
        if raw is None:
            return None
        k = norm_key(raw)
        table, allowed = {
            "traccion": (TRACCION_SYN, self.traccion),
            "combustible": (COMBUSTIBLE_SYN, self.combustible),
            "clasificacion": (CLASIFICACION_SYN, self.clasificacion),
            "caja": (CAJA_SYN, self.caja),
        }[campo]
        val = table.get(k)
        return val if val in allowed else None


def load(path: str | Path = DEFAULT_PATH) -> Vocab:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["Hoja1"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))

    marcas: list[str] = []
    seen_m: set[str] = set()
    modelos: dict[str, list[str]] = {}
    last_marca: str | None = None
    tr, co, cl, ca = set(), set(), set(), set()

    for r in rows:
        marca = (str(r[0]).strip() if r[0] not in (None, "") else "")
        modelo = (str(r[1]).strip() if r[1] not in (None, "") else "")
        if marca:
            last_marca = marca
            if marca not in seen_m:
                seen_m.add(marca)
                marcas.append(marca)
                modelos.setdefault(marca, [])
        if modelo and last_marca:
            modelos.setdefault(last_marca, []).append(modelo)
        # enums (leyenda en primeras filas)
        if r[2]: tr.add(str(r[2]).strip())
        if r[3]: co.add(str(r[3]).strip())
        if r[4]: cl.add(str(r[4]).strip())
        if r[5]: ca.add(str(r[5]).strip())

    v = Vocab(
        marcas=marcas,
        modelos_por_marca=modelos,
        traccion=sorted(tr),
        combustible=sorted(co),
        clasificacion=sorted(cl),
        caja=sorted(ca),
    )
    v._marca_idx = {norm_key(m): m for m in marcas}
    _merge_extra(v, EXTRA_PATH)
    return v


def _merge_extra(v: Vocab, path: str | Path) -> None:
    """Fusiona data/vocab_extra.json: marcas nuevas + alias hacia canónicas."""
    p = Path(path)
    if not p.exists():
        return
    extra = json.loads(p.read_text(encoding="utf-8"))
    for marca, modelos in (extra.get("marcas") or {}).items():
        marca = marca.strip()
        if norm_key(marca) not in v._marca_idx:
            v.marcas.append(marca)
            v._marca_idx[norm_key(marca)] = marca
        v.modelos_por_marca.setdefault(marca, [])
        for mod in modelos or []:
            if mod not in v.modelos_por_marca[marca]:
                v.modelos_por_marca[marca].append(str(mod).strip())
    for alias, canon in (extra.get("aliases") or {}).items():
        canon = canon.strip()
        if norm_key(canon) not in v._marca_idx:
            raise ValueError(f"alias '{alias}' apunta a marca inexistente '{canon}'")
        v._alias_idx[norm_key(alias)] = v._marca_idx[norm_key(canon)]
    # alias de modelo por marca: {marca: {modelo_raw: modelo_canonico}}
    for marca, mapping in (extra.get("model_aliases") or {}).items():
        canon_marca = v._marca_idx.get(norm_key(marca))
        if not canon_marca:
            raise ValueError(f"model_aliases para marca inexistente '{marca}'")
        dst = v._model_alias.setdefault(canon_marca, {})
        for raw, modelo in mapping.items():
            dst[norm_key(raw)] = modelo


if __name__ == "__main__":
    v = load()
    print("marcas:", len(v.marcas))
    print("modelos:", sum(len(x) for x in v.modelos_por_marca.values()))
    print("traccion:", v.traccion)
    print("combustible:", v.combustible)
    print("clasificacion:", v.clasificacion)
    print("caja:", v.caja)
