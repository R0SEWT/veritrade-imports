"""Cache por texto de descripción + checkpoint reanudable en JSONL.

La clave es el hash del texto normalizado (muchas descripciones se repiten por
lote de importación). Cada línea del JSONL es {"key":..., "item":{...crudo LLM...}}.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CACHE_DIR = Path(".cache/llm")
RESULTS = CACHE_DIR / "results.jsonl"


def text_key(desc: str) -> str:
    norm = re.sub(r"\s+", " ", (desc or "").strip().upper())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


class Cache:
    def __init__(self, path: Path = RESULTS):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._mem: dict[str, dict] = {}
        if self.path.exists():
            with self.path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        self._mem[rec["key"]] = rec["item"]
                    except (json.JSONDecodeError, KeyError):
                        continue

    def __contains__(self, key: str) -> bool:
        return key in self._mem

    def get(self, key: str) -> dict | None:
        return self._mem.get(key)

    def put(self, key: str, item: dict) -> None:
        if key in self._mem:
            return
        self._mem[key] = item
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "item": item}, ensure_ascii=False) + "\n")

    def __len__(self) -> int:
        return len(self._mem)
