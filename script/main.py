"""Build and publish a latent ontology graph from Wikipedia articles."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from ontology import (  # noqa: E402
    Neo4jOntologyPublisher,
    OntologyGraph,
    build_ontology_graph,
    load_or_embed_chunks,
    load_or_fetch_articles,
    load_settings,
)

# %%
settings = load_settings()


def run_pipeline(*, force_refresh: bool = False) -> None:
    """Execute the full ingest → embed → extract → publish pipeline."""
    docs = load_or_fetch_articles(settings, force_refresh=force_refresh)
    chunks, embeddings = load_or_embed_chunks(
        docs, settings, force_refresh=force_refresh
    )
    (
        activation_edges,
        concept_nodes,
        similarity_edges,
        hierarchy_edges,
    ) = build_ontology_graph(embeddings, settings)

    Neo4jOntologyPublisher(settings).publish(
        OntologyGraph(
            chunks=chunks,
            concept_nodes=concept_nodes,
            activation_edges=activation_edges,
            similarity_edges=similarity_edges,
            hierarchy_edges=hierarchy_edges,
        )
    )


# %%
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and publish a latent ontology graph to Neo4j."
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore cached articles, chunks, and embeddings.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run_pipeline(force_refresh=_parse_args().force_refresh)
