"""Latent Semantic Attractor Graph — assignment, OMP extraction, mutual k-NN topology.

Pipeline stages implemented here: Assign, Isolate (orphans), Extract (OMP), RELATED_TO topology.
See docs/v2-latent-semantic-attractor-graph/data-flow.md
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.decomposition import MiniBatchDictionaryLearning
from sklearn.metrics.pairwise import cosine_similarity

from v2_orchestrator.settings import Settings
from v2_orchestrator.storage import ConceptStore


def _l2_normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def compute_adaptive_threshold(store: ConceptStore, settings: Settings) -> float:
    k = len(store.embeddings)
    if k < 10:
        return settings.min_assign_threshold

    sim_dist = cosine_similarity(store.embeddings)
    np.fill_diagonal(sim_dist, np.nan)
    # Concept-concept sim runs higher than chunk-concept; percentile is a loose upper bound
    adaptive_thresh = float(np.nanpercentile(sim_dist, settings.adaptive_percentile))
    return min(
        settings.max_assign_threshold,
        max(settings.min_assign_threshold, adaptive_thresh),
    )


def assign_and_update(
    x_centered: np.ndarray,
    global_chunk_ids: list[int],
    store: ConceptStore,
    settings: Settings,
    adaptive_thresh: float,
    batch_id: int,
) -> tuple[list[dict[str, Any]], list[np.ndarray], list[int]]:
    activations: list[dict[str, Any]] = []
    orphan_embs: list[np.ndarray] = []
    orphan_ids: list[int] = []

    if len(store.embeddings) == 0:
        for i in range(len(x_centered)):
            orphan_embs.append(x_centered[i])
            orphan_ids.append(global_chunk_ids[i])
        return activations, orphan_embs, orphan_ids

    sims = cosine_similarity(x_centered, store.embeddings)

    for i in range(len(x_centered)):
        best_idx = int(np.argmax(sims[i]))
        best_score = float(sims[i, best_idx])

        if best_score >= adaptive_thresh:
            top_k_indices = np.argsort(sims[i])[-settings.top_k_assign :]
            for tgt_idx in top_k_indices:
                score = float(sims[i, tgt_idx])
                if (
                    score >= (best_score * settings.mixture_ratio)
                    and score >= adaptive_thresh
                ):
                    activations.append(
                        {
                            "chunk_id": global_chunk_ids[i],
                            "concept_id": store.concept_ids[tgt_idx],
                            "weight": score,
                        }
                    )
                    store.update_concept_centroid(
                        tgt_idx, x_centered[i], settings.centroid_alpha, batch_id
                    )
        else:
            orphan_embs.append(x_centered[i])
            orphan_ids.append(global_chunk_ids[i])

    return activations, orphan_embs, orphan_ids


def assign_orphans_nearest(
    orphan_embeddings: np.ndarray,
    orphan_chunk_ids: list[int] | np.ndarray,
    store: ConceptStore,
    settings: Settings,
    batch_id: int,
) -> list[dict[str, Any]]:
    """Wire lone orphans to their nearest attractor when OMP buffer is too small."""
    if len(orphan_embeddings) == 0 or len(store.embeddings) == 0:
        return []

    sims = cosine_similarity(orphan_embeddings, store.embeddings)
    activations: list[dict[str, Any]] = []
    ids = list(orphan_chunk_ids)
    for i in range(len(orphan_embeddings)):
        best_idx = int(np.argmax(sims[i]))
        score = float(sims[i, best_idx])
        activations.append(
            {
                "chunk_id": int(ids[i]),
                "concept_id": store.concept_ids[best_idx],
                "weight": score,
            }
        )
        store.update_concept_centroid(
            best_idx, orphan_embeddings[i], settings.centroid_alpha, batch_id
        )
    return activations


def soft_merge_orphans(
    new_centroids: np.ndarray,
    store: ConceptStore,
    settings: Settings,
) -> tuple[np.ndarray, dict[int, int]]:
    if len(store.embeddings) == 0:
        return new_centroids, {}

    kept_centroids: list[np.ndarray] = []
    absorptions: dict[int, int] = {}
    sims = cosine_similarity(new_centroids, store.embeddings)

    for i in range(len(new_centroids)):
        best_idx = int(np.argmax(sims[i]))
        best_sim = float(sims[i, best_idx])
        if best_sim > settings.soft_merge_low:
            absorptions[i] = store.concept_ids[best_idx]
        else:
            kept_centroids.append(new_centroids[i])

    dim = new_centroids.shape[1] if new_centroids.size else 384
    kept = (
        np.array(kept_centroids, dtype=np.float32)
        if kept_centroids
        else np.empty((0, dim))
    )
    return kept, absorptions


def route_absorbed_activations(
    local_acts: list[dict[str, Any]],
    absorptions: dict[int, int],
    global_chunk_ids: list[int] | np.ndarray,
    buffer_embeddings: np.ndarray,
    store: ConceptStore,
    settings: Settings,
    batch_id: int,
) -> list[dict[str, Any]]:
    """Re-map absorbed OMP concepts to existing attractors and update centroids."""
    routed: list[dict[str, Any]] = []
    for edge in local_acts:
        local_concept = edge["concept_id"]
        if local_concept not in absorptions:
            continue
        global_chunk_id = int(global_chunk_ids[edge["chunk_id"]])
        global_concept_id = absorptions[local_concept]
        routed.append(
            {
                "chunk_id": global_chunk_id,
                "concept_id": global_concept_id,
                "weight": edge["weight"],
            }
        )
        store_idx = store.concept_ids.index(global_concept_id)
        store.update_concept_centroid(
            store_idx,
            buffer_embeddings[edge["chunk_id"]],
            settings.centroid_alpha,
            batch_id,
        )
    return routed


def build_kept_local_to_global(
    n_local_concepts: int,
    absorptions: dict[int, int],
    new_global_ids: list[int],
) -> dict[int, int]:
    mapping: dict[int, int] = {}
    kept_j = 0
    for local_i in range(n_local_concepts):
        if local_i in absorptions:
            continue
        mapping[local_i] = new_global_ids[kept_j]
        kept_j += 1
    return mapping


def remap_activation_edges(
    edges: list[dict[str, Any]],
    *,
    chunk_id_map: list[int] | np.ndarray,
    concept_id_map: list[int] | np.ndarray | dict[int, int],
    skip_absorbed: dict[int, int] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for edge in edges:
        if skip_absorbed and edge["concept_id"] in skip_absorbed:
            continue
        if isinstance(concept_id_map, dict):
            cid = concept_id_map[edge["concept_id"]]
        else:
            cid = int(concept_id_map[edge["concept_id"]])
        out.append(
            {
                "chunk_id": int(chunk_id_map[edge["chunk_id"]]),
                "concept_id": int(cid),
                "weight": edge["weight"],
            }
        )
    return out


def calculate_knn_topology(
    store: ConceptStore, settings: Settings
) -> list[dict[str, Any]]:
    """Mutual k-NN RELATED_TO edges — both concepts must be in each other's top-k."""
    embeddings = store.embeddings
    n = len(embeddings)
    if n < 2:
        return []

    sim_matrix = cosine_similarity(embeddings)
    np.fill_diagonal(sim_matrix, -1)
    peer_count = min(settings.related_to_peer_count, n - 1)
    top_k_mask = np.argsort(sim_matrix, axis=1)[:, -peer_count:]

    seen: set[tuple[int, int]] = set()
    edges: list[dict[str, Any]] = []

    for src_idx in range(n):
        for tgt_idx in top_k_mask[src_idx]:
            if src_idx not in top_k_mask[tgt_idx]:
                continue
            weight = float(sim_matrix[src_idx, tgt_idx])
            if weight <= settings.related_to_min_weight:
                continue
            src_id = int(store.concept_ids[src_idx])
            tgt_id = int(store.concept_ids[tgt_idx])
            key = (min(src_id, tgt_id), max(src_id, tgt_id))
            if key not in seen:
                seen.add(key)
                edges.append({"source": key[0], "target": key[1], "weight": weight})
    return edges


def _build_local_activations(
    coefficients_abs: np.ndarray,
    concepts_per_chunk: int,
) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for chunk_index in range(len(coefficients_abs)):
        top_indices = np.argsort(coefficients_abs[chunk_index])[-concepts_per_chunk:]
        for concept_index in top_indices:
            weight = float(coefficients_abs[chunk_index, concept_index])
            if weight > 1e-5:
                edges.append(
                    {
                        "chunk_id": chunk_index,
                        "concept_id": int(concept_index),
                        "weight": weight,
                    }
                )
    return edges


def _omp_fallback_unit_norm_rows(
    embeddings: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    """When K-sweep is ill-conditioned (tiny orphan buffer), mint one concept per row."""
    centroids = _l2_normalize_rows(embeddings.astype(np.float64)).astype(np.float32)
    n = len(centroids)
    counts = np.ones(n, dtype=np.int64)
    local_acts = [
        {"chunk_id": i, "concept_id": i, "weight": 1.0} for i in range(n)
    ]
    print(f"OMP small-buffer fallback: {n} unit-norm concept(s)")
    return centroids, counts, local_acts


def _omp_extract(
    embeddings: np.ndarray, settings: Settings
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    """K-sweep OMP; returns (centroid_embeddings, chunk_counts, local_acts)."""
    if len(embeddings) == 0:
        return np.empty((0, 0)), np.empty(0, dtype=np.int64), []

    n_samples = len(embeddings)
    if n_samples < settings.dictionary_k_min:
        return _omp_fallback_unit_norm_rows(embeddings)

    actual_batch_size = min(settings.dictionary_batch_size, n_samples)
    concepts_per_chunk = settings.concepts_per_chunk
    effective_k_min = max(2, min(settings.dictionary_k_min, n_samples))
    k_upper = min(settings.max_concept_count, n_samples)
    k_step = max(1, settings.dictionary_k_step)

    best_coefficients = None
    best_dictionary = None
    last_coefficients = None
    last_dictionary = None
    previous_error = float("inf")
    selected_k = effective_k_min
    matrix_norm_sq = np.linalg.norm(embeddings, "fro") ** 2

    for k in range(effective_k_min, k_upper + 1, k_step):
        dictionary_learner = MiniBatchDictionaryLearning(
            n_components=k,
            transform_algorithm="omp",
            transform_n_nonzero_coefs=concepts_per_chunk,
            batch_size=actual_batch_size,
            random_state=settings.random_seed,
        )
        coefficients = dictionary_learner.fit_transform(embeddings)
        dictionary = dictionary_learner.components_
        last_coefficients = coefficients
        last_dictionary = dictionary

        reconstruction = coefficients @ dictionary
        reconstruction_error = (
            np.linalg.norm(embeddings - reconstruction, "fro") ** 2 / matrix_norm_sq
        )

        concept_usage = np.sum(np.abs(coefficients) > 1e-5, axis=0)
        dead_ratio = int(np.sum(concept_usage == 0)) / k
        improvement = previous_error - reconstruction_error

        print(
            f" -> K={k:03d} | Error: {reconstruction_error:.4f} | "
            f"Dead: {dead_ratio * 100:.1f}% | "
            f"Improvement: {improvement if previous_error != float('inf') else 0:.4f}"
        )

        if dead_ratio > settings.max_dead_concept_ratio:
            if best_coefficients is not None:
                print(f"Stopping at dead-node limit; reverting to K={selected_k}")
                break
            continue

        dynamic_tolerance = settings.reconstruction_error_tolerance + (
            dead_ratio * settings.dead_concept_penalty
        )

        if previous_error != float("inf") and improvement < dynamic_tolerance:
            best_coefficients = coefficients
            best_dictionary = dictionary
            selected_k = k
            print(
                f"Stopping: improvement {improvement:.4f} < "
                f"threshold {dynamic_tolerance:.4f}"
            )
            break

        best_coefficients = coefficients
        best_dictionary = dictionary
        selected_k = k
        previous_error = reconstruction_error

    if best_coefficients is None or best_dictionary is None:
        if last_coefficients is not None and last_dictionary is not None:
            print("OMP: using last K attempt (dead-node limit on all swept K)")
            best_coefficients = last_coefficients
            best_dictionary = last_dictionary
        else:
            return _omp_fallback_unit_norm_rows(embeddings)

    coefficients_abs = np.abs(best_coefficients)
    concept_usage = np.sum(coefficients_abs > 1e-5, axis=0)
    active_indices = np.where(concept_usage > 0)[0]
    coefficients_abs = coefficients_abs[:, active_indices]
    dictionary = best_dictionary[active_indices, :]
    omp_chunk_counts = np.sum(coefficients_abs > 1e-5, axis=0).astype(np.int64)

    centroid_embeddings = _l2_normalize_rows(dictionary.astype(np.float64)).astype(
        np.float32
    )
    local_acts = _build_local_activations(coefficients_abs, concepts_per_chunk)

    print(f"OMP selected K={selected_k}, active concepts={len(active_indices)}")
    return centroid_embeddings, omp_chunk_counts, local_acts


def cold_start_extract(
    embeddings: np.ndarray, settings: Settings
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    return _omp_extract(embeddings, settings)


def extract_orphans_omp(
    buffer_embeddings: np.ndarray, settings: Settings
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    return _omp_extract(buffer_embeddings, settings)
