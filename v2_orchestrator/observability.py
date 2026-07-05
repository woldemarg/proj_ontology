"""Batch observability — structured metrics, invariants, and health warnings."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from v2_orchestrator.chunk_journal import ChunkJournal
from v2_orchestrator.paths import data_state_dir
from v2_orchestrator.storage import ConceptStore

METRICS_CSV_HEADER = [
    "batch_id",
    "elapsed_s",
    "ingested",
    "assigned_instant",
    "orphaned",
    "orphan_rate",
    "total_concepts",
    "new_extracted",
    "new_kept",
    "soft_merged",
    "extraction_yield",
    "related_to_edges",
    "avg_degree",
    "max_concept_density_pct",
    "centroid_drift",
    "adaptive_thresh",
    "warnings",
]


@dataclass
class ExtractionStats:
    extracted: int = 0
    kept: int = 0
    soft_merged: int = 0


@dataclass
class BatchMetrics:
    batch_id: int
    elapsed_s: float = 0.0
    ingested: int = 0
    assigned_instant: int = 0
    orphaned: int = 0
    orphan_rate: float = 0.0
    total_concepts: int = 0
    new_extracted: int = 0
    new_kept: int = 0
    soft_merged: int = 0
    extraction_yield: float | None = None
    related_to_edges: int = 0
    avg_degree: float = 0.0
    max_concept_density_pct: float = 0.0
    centroid_drift: float | None = None
    adaptive_thresh: float | None = None
    warnings: list[str] = field(default_factory=list)


class MetricsRecorder:
    def __init__(self, csv_path: Path | None = None) -> None:
        self.csv_path = csv_path or (data_state_dir() / "metrics.csv")
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.csv_path.exists():
            with self.csv_path.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(METRICS_CSV_HEADER)

    def append(self, metrics: BatchMetrics) -> None:
        with self.csv_path.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(
                [
                    metrics.batch_id,
                    f"{metrics.elapsed_s:.3f}",
                    metrics.ingested,
                    metrics.assigned_instant,
                    metrics.orphaned,
                    f"{metrics.orphan_rate:.4f}",
                    metrics.total_concepts,
                    metrics.new_extracted,
                    metrics.new_kept,
                    metrics.soft_merged,
                    ""
                    if metrics.extraction_yield is None
                    else f"{metrics.extraction_yield:.4f}",
                    metrics.related_to_edges,
                    f"{metrics.avg_degree:.3f}",
                    f"{metrics.max_concept_density_pct:.4f}",
                    ""
                    if metrics.centroid_drift is None
                    else f"{metrics.centroid_drift:.6f}",
                    ""
                    if metrics.adaptive_thresh is None
                    else f"{metrics.adaptive_thresh:.4f}",
                    "; ".join(metrics.warnings),
                ]
            )


def snapshot_embeddings(store: ConceptStore) -> np.ndarray | None:
    if store.embeddings.size == 0:
        return None
    return store.embeddings.copy()


def mean_centroid_drift(
    before: np.ndarray | None, after: np.ndarray, dirty_indices: set[int]
) -> float | None:
    if before is None or not dirty_indices:
        return None
    dists = [
        float(np.linalg.norm(after[i] - before[i]))
        for i in dirty_indices
        if i < len(before) and i < len(after)
    ]
    return float(np.mean(dists)) if dists else None


def avg_related_to_degree(edge_count: int, concept_count: int) -> float:
    if concept_count == 0:
        return 0.0
    return (edge_count * 2) / concept_count


def max_concept_density_pct(store: ConceptStore) -> float:
    total = store.next_chunk_id
    if total == 0 or len(store.chunk_counts) == 0:
        return 0.0
    return float(np.max(store.chunk_counts)) / total * 100.0


def apply_health_warnings(metrics: BatchMetrics) -> None:
    if metrics.orphan_rate > 0.50:
        metrics.warnings.append(f"orphan_rate>{50}% ({metrics.orphan_rate:.1%})")
    if metrics.extraction_yield is not None and metrics.extraction_yield < 0.10:
        metrics.warnings.append(
            f"extraction_yield<{10}% ({metrics.extraction_yield:.1%})"
        )
    if metrics.total_concepts > 0:
        # Mutual k-NN: effective degree scales with RELATED_TO_PEER_COUNT (7 → ~4–5 typical).
        if metrics.avg_degree < 1.0:
            metrics.warnings.append(f"avg_degree<{1.0} ({metrics.avg_degree:.2f})")
        elif metrics.avg_degree > 8.0:
            metrics.warnings.append(f"avg_degree>{8.0} ({metrics.avg_degree:.2f})")
    if metrics.max_concept_density_pct > 25.0:
        metrics.warnings.append(
            f"max_hub>{25}% of corpus ({metrics.max_concept_density_pct:.1f}%)"
        )


def log_batch_summary(metrics: BatchMetrics) -> None:
    thresh = (
        f"{metrics.adaptive_thresh:.4f}"
        if metrics.adaptive_thresh is not None
        else "n/a"
    )
    if metrics.new_extracted:
        if metrics.batch_id == 0:
            extract_line = (
                f"Cold start OMP: {metrics.new_extracted} concepts seeded"
            )
        else:
            extract_line = (
                f"Buffer triggered: {metrics.new_extracted} extracted, "
                f"{metrics.new_kept} kept, {metrics.soft_merged} soft-merged"
            )
    else:
        extract_line = "No orphan extraction this batch"
    print(
        f"\n[BATCH {metrics.batch_id}] Processed {metrics.ingested} chunks "
        f"in {metrics.elapsed_s:.1f}s"
    )
    print(
        f" -> CHUNKS  : {metrics.ingested} ingested | "
        f"{metrics.assigned_instant} assigned instantly | "
        f"{metrics.orphaned} routed to orphan buffer ({metrics.orphan_rate:.1%})"
    )
    print(f" -> CONCEPTS: {metrics.total_concepts} total | {extract_line}")
    print(
        f" -> GRAPH   : {metrics.total_concepts} nodes | "
        f"{metrics.related_to_edges} RELATED_TO edges | "
        f"Avg Degree: {metrics.avg_degree:.1f} | "
        f"adaptive_thresh={thresh}"
    )
    if metrics.centroid_drift is not None:
        print(f" -> DRIFT   : mean centroid L2 drift = {metrics.centroid_drift:.5f}")
    if metrics.warnings:
        print(f" -> WARN    : {'; '.join(metrics.warnings)}")


def check_batch_invariants(
    store: ConceptStore,
    journal: ChunkJournal,
    batch_chunk_ids: list[int],
    batch_activations: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []

    if journal.row_count() != store.next_chunk_id:
        errors.append(
            f"chunk conservation: journal={journal.row_count()} "
            f"store.next_chunk_id={store.next_chunk_id}"
        )

    chunks_emb = journal.load_embeddings()
    if chunks_emb.shape[0] != journal.row_count():
        errors.append(
            f"embeddings rows={chunks_emb.shape[0]} != journal={journal.row_count()}"
        )

    activated = {int(a["chunk_id"]) for a in batch_activations}
    missing = [cid for cid in batch_chunk_ids if cid not in activated]
    if missing:
        errors.append(
            f"{len(missing)} batch chunks lack ACTIVATES edges (e.g. ids {missing[:5]})"
        )

    zero_concepts = np.where(store.chunk_counts == 0)[0]
    if len(zero_concepts):
        errors.append(f"{len(zero_concepts)} concepts have chunk_count=0")

    if store.embeddings.size:
        norms = np.linalg.norm(store.embeddings, axis=1)
        if not np.allclose(norms, 1.0, atol=1e-3):
            bad = int(np.sum(np.abs(norms - 1.0) > 1e-3))
            errors.append(f"{bad} concept embeddings not unit-norm")

    return errors


def check_post_run_invariants(
    store: ConceptStore,
    journal: ChunkJournal,
    neo4j_chunk_count: int,
    neo4j_concept_count: int,
    orphan_chunks_neo4j: int,
    orphan_concepts_neo4j: int,
) -> list[str]:
    errors: list[str] = []

    if journal.row_count() != store.next_chunk_id:
        errors.append(
            f"chunks: journal={journal.row_count()} != store={store.next_chunk_id}"
        )
    if neo4j_chunk_count != store.next_chunk_id:
        errors.append(
            f"chunks: neo4j={neo4j_chunk_count} != store={store.next_chunk_id}"
        )
    if neo4j_concept_count != len(store.concept_ids):
        errors.append(
            f"concepts: neo4j={neo4j_concept_count} != store={len(store.concept_ids)}"
        )
    if orphan_chunks_neo4j:
        errors.append(f"{orphan_chunks_neo4j} Neo4j chunks without ACTIVATES")
    if orphan_concepts_neo4j:
        errors.append(f"{orphan_concepts_neo4j} Neo4j concepts without ACTIVATES")
    if len(store.chunk_counts) and int(np.min(store.chunk_counts)) == 0:
        errors.append("store has concepts with chunk_count=0")

    return errors
