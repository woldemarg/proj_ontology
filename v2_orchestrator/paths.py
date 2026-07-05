"""Path helpers for the v2_orchestrator package."""

from __future__ import annotations

import os
from pathlib import Path


def package_root() -> Path:
    return Path(__file__).resolve().parent


def resolve_project_root() -> Path:
    env_root = os.environ.get("PROJECT_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return package_root().parent


def data_cache_dir() -> Path:
    return package_root() / "data" / "cache"


def data_state_dir() -> Path:
    return package_root() / "data" / "state"


def visualisation_artifacts_dir() -> Path:
    return package_root() / "data" / "visualisation" / "artifacts"


def model_cache_dir() -> Path:
    return resolve_project_root() / "models" / "sentence-transformers"


def cypher_dir() -> Path:
    override = os.environ.get("V2_CYPHER_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return package_root() / "cypher"
