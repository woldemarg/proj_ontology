"""Environment-backed runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ontology.paths import resolve_project_root


def _load_dotenv(path: Path) -> None:
    """Populate os.environ from a .env file without overwriting existing keys."""
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _env_str(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    return int(os.environ.get(key, str(default)))


def _env_float(key: str, default: float) -> float:
    return float(os.environ.get(key, str(default)))


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    # Neo4j
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str
    neo4j_delete_batch_size: int
    neo4j_load_batch_size: int

    # Embedding pipeline
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    embed_batch_size: int

    # Ontology extraction
    concepts_per_chunk: int
    related_to_peer_count: int
    related_to_min_weight: float
    max_concept_count: int
    dictionary_k_min: int
    dictionary_k_step: int
    reconstruction_error_tolerance: float
    dead_concept_penalty: float
    max_dead_concept_ratio: float
    dictionary_batch_size: int
    louvain_resolution: float
    random_seed: int

    # Wikipedia ingestion
    wikipedia_max_retries: int
    wikipedia_request_delay_seconds: float
    wikipedia_user_agent: str

    # Cache filenames
    docs_cache_file: str
    chunks_cache_file: str
    embeddings_cache_file: str
    embed_manifest_file: str

    # Visualisation (optional artifacts under data/visualisation/)
    keep_visual_artifacts: bool
    draw_edges: bool
    edge_auto_disable_chunk_threshold: int


def load_settings(env_file: Path | None = None) -> Settings:
    """Load settings from .env (if present) and environment variables."""
    dotenv_path = env_file or (resolve_project_root() / ".env")
    _load_dotenv(dotenv_path)

    return Settings(
        neo4j_uri=_env_str("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=_env_str("NEO4J_USER", "neo4j"),
        neo4j_password=_env_str("NEO4J_PASSWORD", "password"),
        neo4j_database=_env_str("NEO4J_DATABASE", "ontology2"),
        neo4j_delete_batch_size=_env_int("NEO4J_DELETE_BATCH_SIZE", 10_000),
        neo4j_load_batch_size=_env_int("NEO4J_LOAD_BATCH_SIZE", 5_000),
        embedding_model=_env_str(
            "EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
        ),
        chunk_size=_env_int("CHUNK_SIZE", 1024),
        chunk_overlap=_env_int("CHUNK_OVERLAP", 128),
        embed_batch_size=_env_int("EMBED_BATCH_SIZE", 64),
        concepts_per_chunk=_env_int("CONCEPTS_PER_CHUNK", 2),
        related_to_peer_count=_env_int("RELATED_TO_PEER_COUNT", 5),
        related_to_min_weight=_env_float("RELATED_TO_MIN_WEIGHT", 0.15),
        max_concept_count=_env_int("MAX_CONCEPT_COUNT", 200),
        dictionary_k_min=_env_int("DICTIONARY_K_MIN", 20),
        dictionary_k_step=_env_int("DICTIONARY_K_STEP", 20),
        reconstruction_error_tolerance=_env_float(
            "RECONSTRUCTION_ERROR_TOLERANCE", 0.015
        ),
        dead_concept_penalty=_env_float("DEAD_CONCEPT_PENALTY", 0.05),
        max_dead_concept_ratio=_env_float("MAX_DEAD_CONCEPT_RATIO", 0.25),
        dictionary_batch_size=_env_int("DICTIONARY_BATCH_SIZE", 256),
        louvain_resolution=_env_float("LOUVAIN_RESOLUTION", 1.0),
        random_seed=_env_int("RANDOM_SEED", 42),
        wikipedia_max_retries=_env_int("WIKIPEDIA_MAX_RETRIES", 3),
        wikipedia_request_delay_seconds=_env_float(
            "WIKIPEDIA_REQUEST_DELAY_SECONDS", 1.5
        ),
        wikipedia_user_agent=_env_str(
            "WIKIPEDIA_USER_AGENT",
            "proj-ontology/1.0 (ontology research POC)",
        ),
        docs_cache_file=_env_str("DOCS_CACHE_FILE", "wikipedia_docs.json"),
        chunks_cache_file=_env_str("CHUNKS_CACHE_FILE", "chunks.json"),
        embeddings_cache_file=_env_str("EMBEDDINGS_CACHE_FILE", "embeddings.npy"),
        embed_manifest_file=_env_str("EMBED_MANIFEST_FILE", "embed_manifest.json"),
        keep_visual_artifacts=_env_bool("KEEP_VISUAL_ARTIFACTS", False),
        draw_edges=_env_bool("DRAW_EDGES", True),
        edge_auto_disable_chunk_threshold=_env_int(
            "EDGE_AUTO_DISABLE_CHUNK_THRESHOLD", 5000
        ),
    )
