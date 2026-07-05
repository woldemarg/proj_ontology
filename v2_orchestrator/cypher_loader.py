"""Load Cypher query files from v2_orchestrator/cypher."""

from __future__ import annotations

from functools import lru_cache

from v2_orchestrator.paths import cypher_dir


@lru_cache(maxsize=None)
def load_cypher(query_name: str) -> str:
    path = cypher_dir() / f"{query_name}.cypher"
    if not path.is_file():
        raise FileNotFoundError(f"Cypher query not found: {path}")
    return path.read_text(encoding="utf-8").strip()
