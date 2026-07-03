"""Project path helpers."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_project_root() -> Path:
    """Resolve project root when run as a script, notebook, or line-by-line."""
    env_root = os.environ.get("PROJECT_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    try:
        return Path(__file__).resolve().parent.parent.parent
    except NameError:
        pass

    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "script").is_dir():
            return candidate
    return cwd


def script_dir() -> Path:
    return resolve_project_root() / "script"


def model_cache_dir() -> Path:
    return resolve_project_root() / "models" / "sentence-transformers"


def data_cache_dir() -> Path:
    return resolve_project_root() / "data" / "cache"


def cypher_dir() -> Path:
    override = os.environ.get("ONTOLOGY_CYPHER_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return script_dir() / "cypher"
