"""Neo4j and end-to-end verification for the Latent Semantic Attractor Graph."""

from __future__ import annotations

import numpy as np
from neo4j import GraphDatabase

from v2_orchestrator.chunk_journal import ChunkJournal
from v2_orchestrator.neo4j_uploader import Neo4jOntologyPublisher, OntologyBatch
from v2_orchestrator.observability import check_post_run_invariants
from v2_orchestrator.ontology_engine import calculate_knn_topology
from v2_orchestrator.settings import Settings
from v2_orchestrator.storage import ConceptStore


def sync_store_to_neo4j(
    settings: Settings, store: ConceptStore, journal: ChunkJournal
) -> None:
    """Backfill Neo4j from on-disk state + journal."""
    publisher = Neo4jOntologyPublisher(settings)
    publisher.ensure_constraints()
    try:
        all_indices = set(range(len(store.concept_ids)))
        chunks, _ = journal.materialize_numpy_cache()
        activations = journal.load_activations()
        edges = calculate_knn_topology(store, settings)
        batch_id = max(0, store.processed_topic_offset - 1)
        publisher.upsert_batch(
            OntologyBatch(
                chunks=chunks,
                concept_nodes=store.concept_records_for_neo4j(all_indices),
                activation_edges=activations,
            )
        )
        publisher.upsert_topology(edges, batch_id=batch_id)
        print(
            f"Synced {len(chunks)} chunks, {len(all_indices)} concepts, "
            f"{len(activations)} activations, {len(edges)} RELATED_TO edges"
        )
    finally:
        publisher.close()


def _neo4j_session(settings: Settings):
    driver = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )
    return driver, settings.neo4j_database


def run_neo4j_checks(settings: Settings) -> list[str]:
    driver, db = _neo4j_session(settings)
    errors: list[str] = []

    def q(cypher: str, **params):
        with driver.session(database=db) as session:
            return session.run(cypher, **params).data()

    print(f"=== Neo4j checks ({db}) ===")

    counts = {
        r["label"]: r["c"]
        for r in q("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS c")
    }
    print(f"Nodes: {counts}")
    rels = {
        r["type"]: r["c"]
        for r in q("MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS c")
    }
    print(f"Relationships: {rels}")

    missing = q(
        """
        MATCH (c:Concept)
        WHERE c.chunk_count IS NULL OR c.created_at IS NULL OR c.embedding IS NULL
        RETURN count(c) AS missing
        """
    )[0]["missing"]
    if missing:
        errors.append(f"{missing} concepts missing aging/embedding fields")
    else:
        print("OK: all Concept nodes have chunk_count, created_at, embedding")

    bad_dir = q(
        """
        MATCH (a:Concept)-[r:RELATED_TO]->(b:Concept)
        WHERE a.id >= b.id
        RETURN count(r) AS c
        """
    )[0]["c"]
    if bad_dir:
        errors.append(f"{bad_dir} RELATED_TO edges violate canonical min(id)->max(id)")
    else:
        print("OK: RELATED_TO canonical direction")

    emb_rows = q("MATCH (c:Concept) RETURN c.embedding AS e LIMIT 20")
    for i, row in enumerate(emb_rows):
        norm = float(np.linalg.norm(np.array(row["e"], dtype=np.float64)))
        if abs(norm - 1.0) > 1e-3:
            errors.append(f"Concept embedding sample {i} norm={norm:.4f}")
    if emb_rows and not any("norm" in e for e in errors):
        print("OK: sampled Concept embeddings are unit norm")

    driver.close()
    return errors


def run_e2e_verification(
    settings: Settings, store: ConceptStore, journal: ChunkJournal
) -> list[str]:
    """Post-run invariant checks: disk state, Neo4j orphans, hub scan."""
    driver, db = _neo4j_session(settings)
    try:
        with driver.session(database=db) as session:
            counts = {
                "chunks": int(
                    session.run("MATCH (c:Chunk) RETURN count(c)").single()[0]
                ),
                "concepts": int(
                    session.run("MATCH (c:Concept) RETURN count(c)").single()[0]
                ),
                "orphan_chunks": int(
                    session.run(
                        "MATCH (c:Chunk) WHERE NOT (c)-[:ACTIVATES]->() RETURN count(c)"
                    ).single()[0]
                ),
                "orphan_concepts": int(
                    session.run(
                        "MATCH (c:Concept) WHERE NOT ()-[:ACTIVATES]->(c) RETURN count(c)"
                    ).single()[0]
                ),
            }
            hubs = [
                dict(row)
                for row in session.run(
                    """
                    MATCH (c:Concept)
                    RETURN c.id AS id, c.chunk_count AS chunk_count
                    ORDER BY c.chunk_count DESC
                    LIMIT 5
                    """
                )
            ]
    finally:
        driver.close()

    print("\n=== E2E verification ===")
    print(
        f"Neo4j: {counts['chunks']} chunks, {counts['concepts']} concepts | "
        f"orphan chunks={counts['orphan_chunks']}, "
        f"orphan concepts={counts['orphan_concepts']}"
    )
    print("Top hubs:")
    total = max(store.next_chunk_id, 1)
    for hub in hubs:
        pct = hub["chunk_count"] / total * 100
        print(f"  id={hub['id']} chunk_count={hub['chunk_count']} ({pct:.1f}%)")

    errors = check_post_run_invariants(
        store,
        journal,
        neo4j_chunk_count=counts["chunks"],
        neo4j_concept_count=counts["concepts"],
        orphan_chunks_neo4j=counts["orphan_chunks"],
        orphan_concepts_neo4j=counts["orphan_concepts"],
    )
    errors.extend(run_neo4j_checks(settings))

    if errors:
        print("E2E FAILED:")
        for err in errors:
            print(f" - {err}")
        return errors

    print("E2E verification passed.")
    return []
