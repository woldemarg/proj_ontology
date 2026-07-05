"""Reset v2_orchestrator disk state and optionally clear a Neo4j database."""

from __future__ import annotations

import shutil
from pathlib import Path

from neo4j import GraphDatabase

from v2_orchestrator.paths import (
    data_cache_dir,
    data_state_dir,
    visualisation_artifacts_dir,
)
from v2_orchestrator.settings import Settings


def _clear_dir_contents(directory: Path) -> None:
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)
        return
    for path in directory.iterdir():
        if path.name == ".gitkeep":
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def reset_local_data() -> None:
    """Remove v2_orchestrator state, journal cache, and viz artifacts."""
    for directory in (
        data_state_dir(),
        data_cache_dir(),
        visualisation_artifacts_dir(),
        visualisation_artifacts_dir().parent,
    ):
        _clear_dir_contents(directory)
    (visualisation_artifacts_dir()).mkdir(parents=True, exist_ok=True)
    metrics = data_state_dir() / "metrics.csv"
    if metrics.exists():
        metrics.unlink()
    print("Cleared v2_orchestrator data/state, data/cache, and visualisation outputs.")


def reset_neo4j_database(settings: Settings) -> None:
    """Delete all nodes and relationships in the configured Neo4j database."""
    driver = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )
    try:
        with driver.session(database=settings.neo4j_database) as session:
            session.run("MATCH (n) DETACH DELETE n")
        print(f"Cleared Neo4j database: {settings.neo4j_database}")
    finally:
        driver.close()


def reset_workspace(settings: Settings, *, clear_neo4j: bool = True) -> None:
    reset_local_data()
    if clear_neo4j:
        reset_neo4j_database(settings)
