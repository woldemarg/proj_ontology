"""Incremental Neo4j MERGE publisher for v2_orchestrator.

MERGE-only: no RELATED_TO deletes when mutual k-NN peers change (accepted trade-off).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from neo4j import GraphDatabase

from v2_orchestrator.cypher_loader import load_cypher
from v2_orchestrator.settings import Settings


@dataclass(frozen=True, slots=True)
class OntologyBatch:
    chunks: list[dict[str, Any]]
    concept_nodes: list[dict[str, Any]]
    activation_edges: list[dict[str, Any]]


class Neo4jOntologyPublisher:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self) -> None:
        self._driver.close()

    def ensure_constraints(self) -> None:
        statements = [
            s.strip() for s in load_cypher("ensure_constraints").split(";") if s.strip()
        ]

        def _tx(tx) -> None:
            for stmt in statements:
                tx.run(stmt)

        with self._driver.session(database=self._settings.neo4j_database) as session:
            session.execute_write(_tx)

    def upsert_batch(self, batch: OntologyBatch) -> None:
        with self._driver.session(database=self._settings.neo4j_database) as session:
            session.execute_write(self._upsert_batch_tx, batch)

    def upsert_topology(
        self, similarity_edges: list[dict[str, Any]], *, batch_id: int
    ) -> None:
        if not similarity_edges:
            return
        with self._driver.session(database=self._settings.neo4j_database) as session:
            session.execute_write(self._upsert_topology_tx, similarity_edges, batch_id)

    def _upsert_topology_tx(self, tx, similarity_edges, batch_id: int) -> None:
        self._batch_unwind(
            tx,
            load_cypher("merge_related_to"),
            "relations",
            similarity_edges,
            self._settings.neo4j_load_batch_size,
            batch_id=batch_id,
        )

    def _upsert_batch_tx(self, tx, batch: OntologyBatch) -> None:
        batch_size = self._settings.neo4j_load_batch_size
        self._batch_unwind(
            tx, load_cypher("merge_chunks"), "chunks", batch.chunks, batch_size
        )
        self._batch_unwind(
            tx,
            load_cypher("merge_concepts"),
            "concepts",
            batch.concept_nodes,
            batch_size,
        )
        self._batch_unwind(
            tx,
            load_cypher("merge_activates"),
            "activations",
            batch.activation_edges,
            batch_size,
        )

    @staticmethod
    def _batch_unwind(
        tx,
        query: str,
        param_name: str,
        rows: list[dict[str, Any]],
        batch_size: int,
        **extra_params: Any,
    ) -> None:
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            tx.run(query, **{param_name: batch}, **extra_params)
