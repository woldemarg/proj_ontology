"""Neo4j upload adapter using external Cypher files."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from neo4j import GraphDatabase

from ontology.cypher_loader import load_cypher
from ontology.settings import Settings


@dataclass(frozen=True, slots=True)
class OntologyGraph:
    chunks: list[dict[str, Any]]
    concept_nodes: list[dict[str, Any]]
    activation_edges: list[dict[str, Any]]
    similarity_edges: list[dict[str, Any]]
    hierarchy_edges: list[dict[str, Any]]


class Neo4jOntologyPublisher:
    """Publish an extracted ontology graph to Neo4j."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def publish(self, graph: OntologyGraph) -> None:
        settings = self._settings
        print(f"\n--- Uploading ontology to Neo4j ({settings.neo4j_uri}) ---")

        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        driver.verify_connectivity()

        try:
            with driver.session(database=settings.neo4j_database) as session:
                nodes_deleted, rels_deleted = session.execute_write(
                    self._drop_all_nodes,
                    settings.neo4j_delete_batch_size,
                )
                print(
                    f"Dropped existing data: {nodes_deleted} nodes, "
                    f"{rels_deleted} relationships removed."
                )

            with driver.session(database=settings.neo4j_database) as session:
                session.execute_write(self._ensure_constraints)

            with driver.session(database=settings.neo4j_database) as session:
                session.execute_write(self._load_graph, graph)
        finally:
            driver.close()

        print("Upload complete! Traversal graph is ready.")

    @staticmethod
    def _drop_all_nodes(tx, batch_size: int) -> tuple[int, int]:
        query = load_cypher("drop_all_nodes")
        total_nodes, total_rels = 0, 0

        while True:
            result = tx.run(query, batch_size=batch_size)
            counters = result.consume().counters
            total_nodes += counters.nodes_deleted
            total_rels += counters.relationships_deleted
            if counters.nodes_deleted == 0:
                break

        return total_nodes, total_rels

    @staticmethod
    def _ensure_constraints(tx) -> None:
        tx.run(load_cypher("ensure_chunk_id_unique"))
        tx.run(load_cypher("ensure_concept_id_unique"))

    def _load_graph(self, tx, graph: OntologyGraph) -> None:
        batch_size = self._settings.neo4j_load_batch_size

        self._batch_unwind(
            tx,
            load_cypher("bulk_create_concepts"),
            "concepts",
            graph.concept_nodes,
            batch_size,
        )
        self._batch_unwind(
            tx,
            load_cypher("bulk_create_chunks"),
            "chunks",
            graph.chunks,
            batch_size,
        )
        self._batch_unwind(
            tx,
            load_cypher("bulk_create_activates"),
            "activations",
            graph.activation_edges,
            batch_size,
        )
        self._batch_unwind(
            tx,
            load_cypher("bulk_create_related_to"),
            "relations",
            graph.similarity_edges,
            batch_size,
        )
        self._batch_unwind(
            tx,
            load_cypher("bulk_create_super_concept_of"),
            "hierarchy_links",
            graph.hierarchy_edges,
            batch_size,
        )

    @staticmethod
    def _batch_unwind(
        tx,
        query: str,
        param_name: str,
        rows: list[dict[str, Any]],
        batch_size: int,
    ) -> None:
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            tx.run(query, **{param_name: batch})
