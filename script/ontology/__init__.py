"""Ontology pipeline package."""

from ontology.pipeline import (
    build_ontology_graph,
    load_or_embed_chunks,
    load_or_fetch_articles,
)
from ontology.settings import Settings, load_settings

__all__ = [
    "Neo4jOntologyPublisher",
    "OntologyGraph",
    "Settings",
    "build_ontology_graph",
    "load_or_embed_chunks",
    "load_or_fetch_articles",
    "load_settings",
]


def __getattr__(name: str):
    if name == "Neo4jOntologyPublisher":
        from ontology.neo4j_uploader import Neo4jOntologyPublisher

        return Neo4jOntologyPublisher
    if name == "OntologyGraph":
        from ontology.neo4j_uploader import OntologyGraph

        return OntologyGraph
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
