"""Environment-backed runtime configuration for v2_orchestrator."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from v2_orchestrator.paths import resolve_project_root


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


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
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str
    neo4j_load_batch_size: int

    embedding_model: str
    hf_token: str
    chunk_size: int
    chunk_overlap: int
    embed_batch_size: int
    articles_per_batch: int

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
    random_seed: int

    centroid_alpha: float
    top_k_assign: int
    mixture_ratio: float
    adaptive_percentile: float
    min_assign_threshold: float
    max_assign_threshold: float
    soft_merge_low: float
    orphan_buffer_min_factor: int

    wikipedia_max_retries: int
    wikipedia_request_delay_seconds: float
    wikipedia_user_agent: str

    keep_visual_artifacts: bool


def load_settings(env_file: Path | None = None) -> Settings:
    dotenv_path = env_file or (resolve_project_root() / ".env")
    _load_dotenv(dotenv_path)

    hf_token = _env_str("HF_TOKEN", "")
    if hf_token:
        os.environ.setdefault("HF_TOKEN", hf_token)
        os.environ.setdefault("HUGGING_FACE_HUB_TOKEN", hf_token)

    return Settings(
        neo4j_uri=_env_str("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=_env_str("NEO4J_USER", "neo4j"),
        neo4j_password=_env_str("NEO4J_PASSWORD", "changeme"),
        neo4j_database=_env_str("NEO4J_DATABASE", "ontologyv2"),
        neo4j_load_batch_size=_env_int("NEO4J_LOAD_BATCH_SIZE", 5_000),
        embedding_model=_env_str(
            "EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
        ),
        hf_token=hf_token,
        chunk_size=_env_int("CHUNK_SIZE", 1024),
        chunk_overlap=_env_int("CHUNK_OVERLAP", 128),
        embed_batch_size=_env_int("EMBED_BATCH_SIZE", 64),
        articles_per_batch=_env_int("ARTICLES_PER_BATCH", 2),
        concepts_per_chunk=_env_int("CONCEPTS_PER_CHUNK", 2),
        related_to_peer_count=_env_int("RELATED_TO_PEER_COUNT", 7),
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
        random_seed=_env_int("RANDOM_SEED", 42),
        centroid_alpha=_env_float("CENTROID_ALPHA", 0.05),
        top_k_assign=_env_int("TOP_K_ASSIGN", 2),
        mixture_ratio=_env_float("MIXTURE_RATIO", 0.90),
        adaptive_percentile=_env_float("ADAPTIVE_PERCENTILE", 85),
        min_assign_threshold=_env_float("MIN_ASSIGN_THRESHOLD", 0.30),
        max_assign_threshold=_env_float("MAX_ASSIGN_THRESHOLD", 0.45),
        soft_merge_low=_env_float("SOFT_MERGE_LOW", 0.55),
        orphan_buffer_min_factor=_env_int("ORPHAN_BUFFER_MIN_FACTOR", 3),
        wikipedia_max_retries=_env_int("WIKIPEDIA_MAX_RETRIES", 3),
        wikipedia_request_delay_seconds=_env_float(
            "WIKIPEDIA_REQUEST_DELAY_SECONDS", 1.5
        ),
        wikipedia_user_agent=_env_str(
            "WIKIPEDIA_USER_AGENT",
            "proj-ontology/1.0 (Latent Semantic Attractor Graph)",
        ),
        keep_visual_artifacts=_env_bool("KEEP_VISUAL_ARTIFACTS", False),
    )
