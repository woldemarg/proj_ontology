"""Latent Semantic Attractor Graph — streaming batch pipeline.

Online loop: Ingest → Assign → Update (EMA) → Isolate (Orphans) → Extract (OMP) → Upsert (Neo4j).

Docs: v2_orchestrator/README.md · docs/v2-latent-semantic-attractor-graph/data-flow.md
"""

from __future__ import annotations

import argparse
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

from v2_orchestrator.chunk_journal import ChunkJournal
from v2_orchestrator.ingest import WIKIPEDIA_TOPICS, ingest_batch
from v2_orchestrator.neo4j_uploader import Neo4jOntologyPublisher, OntologyBatch
from v2_orchestrator.observability import (
    BatchMetrics,
    ExtractionStats,
    MetricsRecorder,
    apply_health_warnings,
    avg_related_to_degree,
    check_batch_invariants,
    log_batch_summary,
    max_concept_density_pct,
    mean_centroid_drift,
    snapshot_embeddings,
)
from v2_orchestrator.ontology_engine import (
    assign_and_update,
    assign_orphans_nearest,
    build_kept_local_to_global,
    calculate_knn_topology,
    cold_start_extract,
    compute_adaptive_threshold,
    extract_orphans_omp,
    remap_activation_edges,
    route_absorbed_activations,
    soft_merge_orphans,
)
from v2_orchestrator.reset import reset_workspace
from v2_orchestrator.settings import Settings, load_settings
from v2_orchestrator.storage import ConceptStore
from v2_orchestrator import viz_export
from v2_orchestrator.verification import run_e2e_verification


def _assign_global_chunk_ids(chunks: list[dict], store: ConceptStore) -> list[int]:
    global_ids: list[int] = []
    for chunk in chunks:
        chunk["id"] = store.next_chunk_id
        global_ids.append(store.next_chunk_id)
        store.next_chunk_id += 1
    return global_ids


def run_batch(
    store: ConceptStore,
    journal: ChunkJournal,
    publisher: Neo4jOntologyPublisher,
    settings: Settings,
    recorder: MetricsRecorder,
) -> bool:
    """Run one batch. Returns False when no more topics to process."""
    topic_offset = store.processed_topic_offset * settings.articles_per_batch
    if topic_offset >= len(WIKIPEDIA_TOPICS):
        print("All topics processed.")
        return False

    batch_start = time.perf_counter()
    emb_before = snapshot_embeddings(store)
    extraction = ExtractionStats()
    batch_id = store.processed_topic_offset
    cold_start = store.is_empty

    chunks, x_raw = ingest_batch(settings, topic_offset)
    if not chunks:
        print("No chunks in batch — stopping.")
        return False

    x_centered = store.update_global_mean(x_raw)
    global_chunk_ids = _assign_global_chunk_ids(chunks, store)
    batch_activations: list[dict] = []
    orphan_count = 0
    adaptive_thresh: float | None = None

    if cold_start:
        print("Batch 0: cold start OMP extraction...")
        centroid_embeddings, omp_chunk_counts, local_acts = cold_start_extract(
            x_centered, settings
        )
        global_concept_ids = store.bootstrap(
            centroid_embeddings,
            chunk_counts=omp_chunk_counts,
            batch_id=batch_id,
        )
        batch_activations += remap_activation_edges(
            local_acts,
            chunk_id_map=global_chunk_ids,
            concept_id_map=global_concept_ids,
        )
        extraction.extracted = len(centroid_embeddings)
        extraction.kept = len(centroid_embeddings)
    else:
        adaptive_thresh = compute_adaptive_threshold(store, settings)
        print(f"Adaptive threshold: {adaptive_thresh:.4f}")

        activations, orphan_embs, orphan_ids = assign_and_update(
            x_centered,
            global_chunk_ids,
            store,
            settings,
            adaptive_thresh,
            batch_id,
        )
        batch_activations += activations
        orphan_count = len(orphan_ids)

        if orphan_embs:
            store.push_orphans(np.stack(orphan_embs), orphan_ids)

        buffer_size = len(store.orphan_embeddings)
        partial_flush = buffer_size > 0 and not store.orphan_buffer_ready(settings)
        if store.should_extract_orphans(settings, orphan_count):
            buffer_emb, buf_chunk_ids = store.get_orphan_buffer()
            if partial_flush:
                threshold = (
                    settings.dictionary_k_min * settings.orphan_buffer_min_factor
                )
                print(
                    f"Orphan buffer partial flush ({buffer_size}/{threshold}) — OMP extract..."
                )
            else:
                print(f"Orphan buffer ready ({buffer_size} chunks) — OMP extract...")
            new_centroids, omp_chunk_counts, local_acts = extract_orphans_omp(
                buffer_emb, settings
            )
            kept_centroids, absorptions = soft_merge_orphans(
                new_centroids, store, settings
            )
            extraction.extracted = len(new_centroids)
            extraction.soft_merged = len(absorptions)
            extraction.kept = len(kept_centroids)

            batch_activations += route_absorbed_activations(
                local_acts,
                absorptions,
                buf_chunk_ids,
                buffer_emb,
                store,
                settings,
                batch_id,
            )
            if len(kept_centroids) > 0:
                kept_chunk_counts = [
                    int(omp_chunk_counts[i])
                    for i in range(len(new_centroids))
                    if i not in absorptions
                ]
                new_global_ids = store.append_concepts(
                    kept_centroids,
                    chunk_counts=kept_chunk_counts,
                    batch_id=batch_id,
                )
                kept_local_to_global = build_kept_local_to_global(
                    len(new_centroids), absorptions, new_global_ids
                )
                batch_activations += remap_activation_edges(
                    local_acts,
                    chunk_id_map=buf_chunk_ids,
                    concept_id_map=kept_local_to_global,
                    skip_absorbed=absorptions,
                )
            store.clear_orphan_buffer()
        elif orphan_count > 0:
            batch_activations += assign_orphans_nearest(
                np.stack(orphan_embs), orphan_ids, store, settings, batch_id
            )
            store.clear_orphan_buffer()
            print(f"Orphan nearest-attractor fallback ({orphan_count} chunks)")

    similarity_edges = calculate_knn_topology(store, settings)

    publisher.upsert_batch(
        OntologyBatch(
            chunks=chunks,
            concept_nodes=store.concept_records_for_neo4j(store.dirty_concept_indices),
            activation_edges=batch_activations,
        )
    )
    publisher.upsert_topology(similarity_edges, batch_id=batch_id)

    batch_dirty = set(store.dirty_concept_indices)
    store.clear_dirty()

    journal.append_batch(chunks, x_centered, batch_activations)

    invariant_errors = check_batch_invariants(
        store, journal, global_chunk_ids, batch_activations
    )
    if invariant_errors:
        raise RuntimeError(
            "Batch invariant violation:\n  " + "\n  ".join(invariant_errors)
        )

    if settings.keep_visual_artifacts:
        viz_export.materialize(store, journal)

    store.processed_topic_offset += 1
    store.save()

    ingested = len(chunks)
    assigned_instant = ingested if cold_start else ingested - orphan_count

    metrics = BatchMetrics(
        batch_id=batch_id,
        elapsed_s=time.perf_counter() - batch_start,
        ingested=ingested,
        assigned_instant=assigned_instant,
        orphaned=orphan_count,
        orphan_rate=orphan_count / max(ingested, 1),
        total_concepts=len(store.concept_ids),
        new_extracted=extraction.extracted,
        new_kept=extraction.kept,
        soft_merged=extraction.soft_merged,
        extraction_yield=(
            extraction.kept / extraction.extracted if extraction.extracted else None
        ),
        related_to_edges=len(similarity_edges),
        avg_degree=avg_related_to_degree(len(similarity_edges), len(store.concept_ids)),
        max_concept_density_pct=max_concept_density_pct(store),
        centroid_drift=mean_centroid_drift(emb_before, store.embeddings, batch_dirty),
        adaptive_thresh=adaptive_thresh,
    )
    apply_health_warnings(metrics)
    log_batch_summary(metrics)
    recorder.append(metrics)
    return True


def run_batch_loop(
    settings: Settings,
    *,
    max_batches: int | None = None,
    plot: bool = False,
    plot_output: Path | None = None,
    draw_edges: bool | None = None,
    reset: bool = False,
    verify: bool = True,
) -> None:
    if reset:
        reset_workspace(settings)

    store = ConceptStore.load()
    journal = ChunkJournal()
    store.sync_chunk_cursor_from_journal(journal)
    recorder = MetricsRecorder()
    publisher = Neo4jOntologyPublisher(settings)
    publisher.ensure_constraints()

    batches_run = 0
    try:
        while True:
            if max_batches is not None and batches_run >= max_batches:
                break
            if not run_batch(store, journal, publisher, settings, recorder):
                break
            batches_run += 1
    finally:
        publisher.close()

    if plot:
        viz_export.render_sphere_plot(plot_output, draw_edges=draw_edges)

    if verify and batches_run > 0:
        errors = run_e2e_verification(settings, store, journal)
        if errors:
            raise RuntimeError("E2E verification failed")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Latent Semantic Attractor Graph batch pipeline."
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Stop after N batches (default: until topics exhausted).",
    )
    parser.add_argument(
        "--articles-per-batch",
        type=int,
        default=None,
        help="Override ARTICLES_PER_BATCH from settings.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe local v2_orchestrator data and Neo4j database before running.",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="After batches, render ontology_sphere.html from viz artifacts.",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip post-run E2E invariant verification.",
    )
    parser.add_argument(
        "-o",
        "--plot-output",
        type=Path,
        default=None,
        help="HTML output path for --plot.",
    )
    edges = parser.add_mutually_exclusive_group()
    edges.add_argument("--draw-edges", action="store_true")
    edges.add_argument("--no-draw-edges", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    settings = load_settings()
    if args.articles_per_batch is not None:
        settings = replace(settings, articles_per_batch=args.articles_per_batch)

    draw_edges: bool | None = None
    if args.draw_edges:
        draw_edges = True
    elif args.no_draw_edges:
        draw_edges = False

    run_batch_loop(
        settings,
        max_batches=args.max_batches,
        plot=args.plot,
        plot_output=args.plot_output,
        draw_edges=draw_edges,
        reset=args.reset,
        verify=not args.no_verify,
    )


if __name__ == "__main__":
    main()
