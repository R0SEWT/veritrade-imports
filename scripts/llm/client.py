"""Cliente DeepSeek (OpenAI-compatible): batching, concurrencia, retry/backoff.

La API key se lee SOLO de la env var DEEPSEEK_API_KEY. Nunca se hardcodea ni
se loguea. El prefijo (system) es estable para aprovechar el prompt-cache.
"""
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from . import schema
from .cache import Cache, text_key
from .vocab import Vocab

BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")


class EmptyContentError(RuntimeError):
    """DeepSeek a veces devuelve content vacío; reintentable."""


@dataclass
class Stats:
    requests: int = 0
    errors: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, usage) -> None:
        with self._lock:
            self.requests += 1
            if usage:
                self.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
                self.completion_tokens += getattr(usage, "completion_tokens", 0) or 0
                details = getattr(usage, "prompt_tokens_details", None)
                if details:
                    self.cached_tokens += getattr(details, "cached_tokens", 0) or 0


class DeepSeekClient:
    def __init__(self, vocab: Vocab, model: str = DEFAULT_MODEL, batch_size: int = 10,
                 workers: int = 4, max_tokens: int = 4096):
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise SystemExit("Falta DEEPSEEK_API_KEY en el entorno. Exporta tu clave (rotada).")
        from openai import OpenAI  # import diferido
        self.client = OpenAI(api_key=api_key, base_url=BASE_URL)
        self.model = model
        self.batch_size = batch_size
        self.workers = workers
        self.max_tokens = max_tokens
        self.system = schema.build_system_prompt(vocab)
        self.stats = Stats()

    @retry(reraise=True, stop=stop_after_attempt(5),
           wait=wait_exponential(multiplier=1, min=2, max=30),
           retry=retry_if_exception_type((EmptyContentError, Exception)))
    def _call(self, batch: list[tuple[int, str]]) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": self.system},
                {"role": "user", "content": schema.build_user_message(batch)},
            ],
        )
        self.stats.add(getattr(resp, "usage", None))
        content = resp.choices[0].message.content
        if not content or not content.strip():
            raise EmptyContentError("content vacío")
        return content

    def run(self, pairs: list[tuple[str, str]], cache: Cache,
            on_batch=None) -> None:
        """pairs: lista de (text_key, desc) ÚNICOS y NO cacheados. Llena la cache.

        on_batch(content, batch) opcional para validación/checkpoint por batch.
        """
        batches: list[list[tuple[int, str]]] = []
        keymaps: list[dict[int, str]] = []
        for start in range(0, len(pairs), self.batch_size):
            chunk = pairs[start:start + self.batch_size]
            batches.append([(i, desc) for i, (_, desc) in enumerate(chunk)])
            keymaps.append({i: k for i, (k, _) in enumerate(chunk)})

        def work(idx: int):
            content = self._call(batches[idx])
            return idx, content

        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            futs = {ex.submit(work, i): i for i in range(len(batches))}
            for fut in as_completed(futs):
                try:
                    idx, content = fut.result()
                except Exception:
                    self.stats.errors += 1
                    continue
                if on_batch:
                    on_batch(content, batches[idx], keymaps[idx], cache)
