#!/usr/bin/env python3
"""Extracción estructurada de la Descripción Comercial (Veritrade, partida 8704229000).

Enfoque A (determinístico): parser por diccionario de códigos de aduana peruana.
Lee el export xlsx, conserva columnas "duras" y descompone el campo
`Descripción Comercial` en columnas tipadas. Imprime un reporte de cobertura
y escribe la tabla limpia + una hoja `_revisar` con filas de parseo incompleto.

Spec: docs/superpowers/specs/2026-05-30-extraccion-descripcion-comercial-design.md
"""
from __future__ import annotations

import re
import argparse
import sys
from pathlib import Path

import openpyxl

INPUTS_DIR = "inputs"    # carpeta con exports crudos de Veritrade (vehículos)
OUTPUTS_DIR = "outputs"  # carpeta de salida: <stem>_estructurado.xlsx
HEADER_ROW = 6  # banner en filas 1-5, cabecera en la 6, datos desde la 7

# --- Columnas "duras" del export: cabecera original -> nombre de salida ---
HARD_COLS = {
    "Partida Aduanera": "partida",
    "Aduana": "aduana",
    "DUA / DAM": "dua_dam",
    "Fecha": "fecha",
    "Importador": "importador",
    "Embarcador / Exportador": "exportador",
    "Kg Bruto": "kg_bruto",
    "Kg Neto": "kg_neto",
    "U$ FOB Tot": "fob_usd",
    "U$ CFR Tot": "cfr_usd",
    "U$ CIF Tot": "cif_usd",
    "Pais de Origen": "pais_origen",
    "Pais de Compra": "pais_compra",
    "Puerto de Embarque": "puerto_embarque",
    "Via": "via",
    "Agente de Aduana": "agente_aduana",
    "Estado": "estado",
    "Ad Valorem": "ad_valorem",
    "IGV": "igv",
    "ISC": "isc",
    "IPM": "ipm",
    "Fecha Embarque": "fecha_embarque",
    "Descripcion Comercial": "_descripcion",  # fuente del parseo
}

# --- Diccionario de códigos: CÓDIGO -> (columna, tipo) ---
# tipo: text | int | num | power
CODES = {
    "MARCA": ("marca", "text"),
    "MODELO": ("modelo", "text"),
    "VERSION": ("version", "text"),
    "AÑO MOD": ("anio_modelo", "int"),
    "AÑO": ("anio_modelo", "int"),
    "VI": ("vin", "text"),
    "CH": ("chasis", "text"),
    "MO": ("motor_serie", "text"),
    "CO": ("combustible", "text"),  # ¡ambiguo! a veces es color -> se clasifica en _assign
    "COMB": ("combustible", "text"),
    "C1": ("color", "text"),
    "NC": ("num_cilindros", "int"),
    "CC": ("cilindrada_cc", "num"),
    "PM": ("potencia", "power"),
    "EJ": ("ejes", "int"),
    "FR": ("traccion", "text"),
    "TT": ("transmision", "text"),
    "CA": ("carroceria", "text"),
    "AS": ("asientos", "int"),
    "PA": ("puertas", "int"),
    "PB": ("peso_bruto", "num"),
    "PN": ("peso_neto", "num"),
    "CU": ("carga_util", "num"),
    "LA": ("largo_mm", "num"),
    "AN": ("ancho_mm", "num"),
    "AL": ("alto_mm", "num"),
    "DE": ("dist_ejes", "num"),
    "KILOMETRAJE": ("kilometraje", "num"),
}

# Columnas extraídas, en orden de salida
EXTRACTED_ORDER = [
    "categoria", "marca", "modelo", "version", "anio_modelo",
    "vin", "chasis", "motor_serie", "combustible", "color",
    "num_cilindros", "cilindrada_cc", "potencia", "potencia_hp",
    "ejes", "traccion", "transmision", "carroceria", "asientos", "puertas",
    "peso_bruto", "peso_neto", "carga_util",
    "largo_mm", "ancho_mm", "alto_mm", "dist_ejes", "kilometraje",
    "desc_prefijo",  # texto libre antes del primer código (sin marca explícita)
]

# Marcas conocidas de camiones para el heurístico cuando falta "MARCA:".
# Orden importa: multi-palabra primero.
BRANDS = [
    "MERCEDES BENZ", "MERCEDES-BENZ", "MERCEDES", "FREIGHTLINER", "INTERNATIONAL",
    "VOLKSWAGEN", "DONGFENG", "SINOTRUK", "SHACMAN", "KENWORTH", "MITSUBISHI",
    "HYUNDAI", "ISUZU", "SCANIA", "VOLVO", "IVECO", "FOTON", "HOWO", "DAYUN",
    "CHANGAN", "MAXUS", "HINO", "FUSO", "FAW", "JAC", "JMC", "JBC", "MAN",
    "KIA", "DAF", "UD", "TATA", "DFAC", "DFSK", "CAMC", "BEIBEN", "JOYLONG",
]
BRAND_RE = re.compile(r"\b(" + "|".join(re.escape(b) for b in BRANDS) + r")\b", re.I)

# Tokenizador genérico: cualquier "TOKEN:" (incl. CH/VIN) precedido por límite.
# Captura TODO token código-valor, conocido o no, para que un valor termine en
# el siguiente token y no se trague pares desconocidos (SN:, NR:, PP:, ...).
GENERIC_CODE_RE = re.compile(
    r"(?:^|[,;\s])((?:CH/VIN)|[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9.]{0,14})\s*:",
)
CATEGORY_RE = re.compile(r"^\s*(N\d)", re.IGNORECASE)
# Año tolerante: "AÑO MOD:2023", "AÑO:2023", "AÑO  2023", "AÑO MOD 2023"
YEAR_RE = re.compile(r"A[ÑN]O(?:\s*MOD)?\s*:?\s*((?:19|20)\d{2})", re.IGNORECASE)
NUM_RE = re.compile(r"-?\d+(?:[.,]\d+)?")
FUEL_RE = re.compile(r"DIESEL|PETROLEO|GASOLINA|GAS\b|GNV|GLP|ELECTR|H[IÍ]BRID|DUAL|BIODIESEL", re.I)


def to_num(v):
    m = NUM_RE.search(v.replace(",", "."))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def to_int(v):
    n = to_num(v)
    return int(n) if n is not None else None


def parse_descripcion(desc: str) -> dict:
    """Descompone una Descripción Comercial en campos. Determinístico."""
    out = {k: None for k in EXTRACTED_ORDER}
    if not desc:
        return out
    s = str(desc).strip()

    # Categoría (N1/N2/N3)
    mcat = CATEGORY_RE.match(s)
    if mcat:
        out["categoria"] = mcat.group(1).upper()

    # Tokenizar TODOS los pares "CÓDIGO:valor" (conocidos o no)
    matches = list(GENERIC_CODE_RE.finditer(s))

    # Prefijo libre = texto entre la categoría y el primer token
    first_code_pos = matches[0].start(1) if matches else len(s)
    prefix_start = mcat.end() if mcat else 0
    prefix = s[prefix_start:first_code_pos].strip(" ,;-")

    # El valor de cada token termina donde empieza el siguiente token,
    # de modo que un código conocido no absorbe pares desconocidos.
    for i, m in enumerate(matches):
        code = m.group(1).upper()
        if code not in CODES and code != "CH/VIN":
            continue  # token desconocido: actúa como límite, no se guarda
        val_start = m.end()  # después de "código :"
        val_end = matches[i + 1].start(1) if i + 1 < len(matches) else len(s)
        raw = s[val_start:val_end].strip().strip(",;").strip()
        if not raw:
            continue
        _assign(out, code, raw)

    # Año por regex tolerante (cubre el caso sin ":")
    if out["anio_modelo"] is None:
        my = YEAR_RE.search(s)
        if my:
            out["anio_modelo"] = int(my.group(1))

    # Heurístico de marca cuando no vino "MARCA:"
    if not out["marca"]:
        mb = BRAND_RE.search(prefix) or BRAND_RE.search(s)
        if mb:
            out["marca"] = mb.group(1).upper()

    # Conservar el prefijo libre solo si aporta (no hubo MARCA/MODELO explícitos)
    if prefix and (not out["modelo"]):
        out["desc_prefijo"] = prefix

    return out


def _assign(out: dict, code: str, raw: str) -> None:
    if code == "CH/VIN":
        out["chasis"] = out["chasis"] or raw
        out["vin"] = out["vin"] or raw
        return
    if code == "CO":
        # Ambiguo entre exportadores: clasificar por contenido.
        if FUEL_RE.search(raw):
            if out.get("combustible") is None:
                out["combustible"] = raw
        elif out.get("color") is None:
            out["color"] = raw
        return
    col, typ = CODES[code]
    if out.get(col) is not None:
        return  # primera ocurrencia gana
    if typ == "int":
        out[col] = to_int(raw)
    elif typ == "num":
        out[col] = to_num(raw)
    elif typ == "power":
        out[col] = raw  # crudo, p.ej. "132@2500"
        hp = raw.split("@")[0]
        out["potencia_hp"] = to_num(hp)
    else:  # text
        out[col] = raw


def process_file(src: Path, out: Path) -> bool:
    """Parsea un export y escribe out/<...>_estructurado.xlsx. Devuelve True si ok."""
    print(f"\n=== {src.name} ===")
    wb = openpyxl.load_workbook(src, read_only=True)
    ws = wb.active

    # Mapear cabeceras (fila 6) a índices de columna
    header = next(ws.iter_rows(min_row=HEADER_ROW, max_row=HEADER_ROW, values_only=True))
    idx = {name: j for j, name in enumerate(header) if name in HARD_COLS}
    missing = set(HARD_COLS) - set(idx)
    if missing:
        print(f"Advertencia: cabeceras no encontradas: {missing}", file=sys.stderr)

    rows = []
    for row in ws.iter_rows(min_row=HEADER_ROW + 1, values_only=True):
        if all(c is None for c in row):
            continue
        rec = {}
        for orig, out_name in HARD_COLS.items():
            if orig in idx:
                rec[out_name] = row[idx[orig]]
        parsed = parse_descripcion(rec.pop("_descripcion", None))
        rec.update(parsed)
        rows.append(rec)

    if not rows:
        print(f"  Sin filas de datos en {src.name}.", file=sys.stderr)
        return False

    total = len(rows)
    hard_out = [v for k, v in HARD_COLS.items() if v != "_descripcion"]
    columns = hard_out + EXTRACTED_ORDER

    # --- Reporte de cobertura ---
    print(f"\nRegistros procesados: {total}\n")
    print(f"{'CAMPO EXTRAÍDO':<16}{'CON VALOR':>10}{'%':>7}")
    print("-" * 33)
    for col in EXTRACTED_ORDER:
        c = sum(1 for r in rows if r.get(col) not in (None, ""))
        print(f"{col:<16}{c:>10}{100 * c / total:>6.0f}%")

    # Filas a revisar: no se pudo identificar la unidad ni la marca
    revisar = [
        r for r in rows
        if not r.get("vin") and not r.get("chasis") and not r.get("marca")
    ]
    print(f"\nFilas a revisar (sin vin/chasis/marca): {len(revisar)}")

    # --- Escribir xlsx ---
    out_wb = openpyxl.Workbook()
    ws_main = out_wb.active
    ws_main.title = "estructurado"
    ws_main.append(columns)
    for r in rows:
        ws_main.append([r.get(c) for c in columns])

    if revisar:
        ws_rev = out_wb.create_sheet("_revisar")
        rev_cols = ["dua_dam", "estado", "categoria", "desc_prefijo"]
        ws_rev.append(rev_cols)
        for r in revisar:
            ws_rev.append([r.get(c) for c in rev_cols])

    out.parent.mkdir(parents=True, exist_ok=True)
    out_wb.save(out)
    print(f"  Escrito: {out}  ({total} filas, {len(columns)} columnas)")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Parser determinístico de la Descripción Comercial (batch).")
    ap.add_argument("--inputs-dir", default=INPUTS_DIR, help="carpeta con exports crudos (default: inputs/)")
    ap.add_argument("--outputs-dir", default=OUTPUTS_DIR, help="carpeta de salida (default: outputs/)")
    ap.add_argument("--input", help="procesar un solo archivo (override de --inputs-dir)")
    args = ap.parse_args()

    if args.input:
        srcs = [Path(args.input)]
    else:
        srcs = sorted(Path(args.inputs_dir).glob("*.xlsx"))
    if not srcs:
        print(f"No se encontraron .xlsx en {args.inputs_dir}/", file=sys.stderr)
        return 1

    out_dir = Path(args.outputs_dir)
    ok = 0
    for src in srcs:
        if not src.exists():
            print(f"No existe: {src}", file=sys.stderr)
            continue
        out = out_dir / f"{src.stem}_estructurado.xlsx"
        if process_file(src, out):
            ok += 1
    print(f"\nListo: {ok}/{len(srcs)} archivos procesados.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
