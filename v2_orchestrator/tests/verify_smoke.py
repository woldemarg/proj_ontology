"""Offline smoke test for the Latent Semantic Attractor Graph batch loop.

Uses a mock Neo4j publisher when a live database is unavailable.
Run: python -m v2_orchestrator.tests.verify_smoke
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from v2_orchestrator.chunk_journal import ChunkJournal
from v2_orchestrator.main import run_batch
from v2_orchestrator.neo4j_uploader import OntologyBatch
from v2_orchestrator.observability import MetricsRecorder
from v2_orchestrator.settings import Settings, load_settings
from v2_orchestrator.storage import ConceptStore


@dataclass
class MockPublisher:
    """Records upserts without a live Neo4j connection."""

    batches: list[OntologyBatch] = field(default_factory=list)
    topology: list[tuple[list[dict[str, Any]], int]] = field(default_factory=list)

    def ensure_constraints(self) -> None:
        pass

    def upsert_batch(self, batch: OntologyBatch) -> None:
        self.batches.append(batch)

    def upsert_topology(
        self, similarity_edges: list[dict[str, Any]], *, batch_id: int
    ) -> None:
        self.topology.append((similarity_edges, batch_id))

    def close(self) -> None:
        pass


def _assert_unit_norm(rows: np.ndarray, label: str) -> None:
    norms = np.linalg.norm(rows, axis=1)
    if not np.allclose(norms, 1.0, atol=1e-4):
        raise AssertionError(f"{label}: centroids not unit norm")


def _run_verification(settings: Settings, work_dir: Path) -> None:
    state_dir = work_dir / "state"
    cache_dir = work_dir / "cache"
    state_dir.mkdir(parents=True)
    cache_dir.mkdir(parents=True)

    store = ConceptStore()
    journal = ChunkJournal(cache_dir=cache_dir)
    publisher = MockPublisher()
    recorder = MetricsRecorder()

    if not run_batch(store, journal, publisher, settings, recorder):
        raise RuntimeError("Batch 0 did not run")

    assert len(publisher.batches) == 1
    batch0 = publisher.batches[0]
    assert batch0.concept_nodes, "Batch 0 must upsert concepts"
    assert all("created_at" in c for c in batch0.concept_nodes)
    _assert_unit_norm(store.embeddings, "batch 0")

    if publisher.topology:
        edges0, bid0 = publisher.topology[0]
        assert bid0 == 0
        for edge in edges0:
            assert edge["source"] < edge["target"]

    offset_after_b0 = store.processed_topic_offset
    store.save(state_dir)

    store2 = ConceptStore.load(state_dir)
    assert store2.processed_topic_offset == offset_after_b0
    assert len(store2.concept_ids) == len(store.concept_ids)

    publisher2 = MockPublisher()
    recorder2 = MetricsRecorder()
    if not run_batch(store2, journal, publisher2, settings, recorder2):
        raise RuntimeError("Batch 1 did not run")

    assert len(publisher2.batches) == 1
    assert store2.processed_topic_offset == offset_after_b0 + 1

    chunks, embs = journal.materialize_numpy_cache()
    assert len(chunks) == embs.shape[0] == store2.next_chunk_id

    print("Smoke verification passed.")
    print(f"  concepts after 2 batches: {len(store2.concept_ids)}")
    print(f"  chunks journaled: {len(chunks)}")
    print(f"  global_mean dim: {len(store2.global_mean)}")


def main() -> None:
    settings = load_settings()
    work_dir = Path(tempfile.mkdtemp(prefix="lsa_verify_"))
    try:
        print(f"Verification workspace: {work_dir}")
        _run_verification(settings, work_dir)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
