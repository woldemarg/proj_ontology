"""Topological Manifold: build and publish a latent ontology graph (one-shot).

Run: python -m v1_single_pass.main
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from ontology.neo4j_uploader import Neo4jOntologyPublisher, OntologyGraph  # noqa: E402
from ontology.pipeline import (  # noqa: E402
    build_ontology_graph,
    load_or_embed_chunks,
    load_or_fetch_articles,
    save_visual_artifacts,
)
from ontology.settings import load_settings  # noqa: E402


def run_pipeline(*, force_refresh: bool = False) -> None:
    """Execute the full ingest → embed → extract → publish pipeline."""
    settings = load_settings()
    docs = load_or_fetch_articles(settings, force_refresh=force_refresh)
    chunks, embeddings = load_or_embed_chunks(
        docs, settings, force_refresh=force_refresh
    )
    (
        activation_edges,
        concept_nodes,
        similarity_edges,
        hierarchy_edges,
        concept_embeddings,
    ) = build_ontology_graph(embeddings, settings)

    save_visual_artifacts(
        settings,
        concept_embeddings,
        concept_nodes,
        activation_edges,
        num_chunks=len(embeddings),
        embedding_dim=int(embeddings.shape[1]),
    )

    Neo4jOntologyPublisher(settings).publish(
        OntologyGraph(
            chunks=chunks,
            concept_nodes=concept_nodes,
            activation_edges=activation_edges,
            similarity_edges=similarity_edges,
            hierarchy_edges=hierarchy_edges,
        )
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and publish a Topological Manifold graph to Neo4j."
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore cached articles, chunks, and embeddings.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run_pipeline(force_refresh=_parse_args().force_refresh)
