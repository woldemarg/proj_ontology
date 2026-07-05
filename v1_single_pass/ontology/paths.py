"""Project path helpers for v1_single_pass."""

from __future__ import annotations

import os
from pathlib import Path


def v1_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_project_root() -> Path:
    env_root = os.environ.get("PROJECT_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return v1_root().parent


def model_cache_dir() -> Path:
    return resolve_project_root() / "models" / "sentence-transformers"


def data_cache_dir() -> Path:
    return v1_root() / "data" / "cache"


def visualisation_artifacts_dir() -> Path:
    return v1_root() / "data" / "visualisation" / "artifacts"


def cypher_dir() -> Path:
    override = os.environ.get("V1_CYPHER_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return v1_root() / "cypher"
