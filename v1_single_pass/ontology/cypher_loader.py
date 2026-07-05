"""Load Cypher query files from v1_single_pass/cypher."""

from __future__ import annotations

from functools import lru_cache

from ontology.paths import cypher_dir


@lru_cache(maxsize=None)
def load_cypher(query_name: str) -> str:
    """Return the text of a named .cypher file."""
    path = cypher_dir() / f"{query_name}.cypher"
    if not path.is_file():
        raise FileNotFoundError(f"Cypher query not found: {path}")
    return path.read_text(encoding="utf-8").strip()
