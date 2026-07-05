"""ConceptStore — evolving semantic attractors and global embedding origin.

Implements Update (EMA) with concept inertia. See docs/v2-latent-semantic-attractor-graph/concept-inertia.md
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from v2_orchestrator.chunk_journal import ChunkJournal
from v2_orchestrator.paths import data_state_dir
from v2_orchestrator.settings import Settings


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConceptStore:
    """In-memory concept state; chunk history lives on disk via chunk_journal."""

    def __init__(self) -> None:
        self.concept_ids: list[int] = []
        self.embeddings: np.ndarray = np.empty((0, 0), dtype=np.float32)
        self.chunk_counts: np.ndarray = np.empty(0, dtype=np.int64)
        self.last_updated_batch: np.ndarray = np.empty(0, dtype=np.int64)
        self.created_at: list[str] = []

        self.global_mean: np.ndarray = np.empty(0, dtype=np.float64)
        self.total_embedded_chunks: int = 0

        self.orphan_embeddings: list[np.ndarray] = []
        self.orphan_chunk_ids: list[int] = []

        self.next_chunk_id: int = 0
        self.next_concept_id: int = 0
        self.processed_topic_offset: int = 0
        self.dirty_concept_indices: set[int] = set()

    @property
    def is_empty(self) -> bool:
        return len(self.concept_ids) == 0

    def update_global_mean(self, raw_batch: np.ndarray) -> np.ndarray:
        """Center against previous global mean, then update mean from raw batch."""
        if raw_batch.size == 0:
            raise ValueError("raw_batch must not be empty")

        if self.total_embedded_chunks == 0:
            self.global_mean = np.zeros(raw_batch.shape[1], dtype=np.float64)

        old_mean = self.global_mean.copy()
        centered_batch = raw_batch.astype(np.float64) - old_mean
        norms = np.linalg.norm(centered_batch, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        x_centered = (centered_batch / norms).astype(np.float32)

        batch_mean = np.mean(raw_batch.astype(np.float64), axis=0)
        batch_size = len(raw_batch)
        self.total_embedded_chunks += batch_size
        weight = batch_size / self.total_embedded_chunks
        self.global_mean = old_mean + (batch_mean - old_mean) * weight

        return x_centered

    def update_concept_centroid(
        self, concept_idx: int, chunk_vec: np.ndarray, alpha: float, batch_id: int
    ) -> None:
        # Concept inertia: mature attractors resist drift (alpha decays with sqrt(chunk_count))
        decayed_alpha = max(0.01, alpha / np.sqrt(self.chunk_counts[concept_idx] + 1))

        c_old = self.embeddings[concept_idx].astype(np.float64)
        chunk = chunk_vec.astype(np.float64)
        blended = (1.0 - decayed_alpha) * c_old + decayed_alpha * chunk
        norm = np.linalg.norm(blended)
        if norm > 1e-12:
            self.embeddings[concept_idx] = (blended / norm).astype(np.float32)

        self.chunk_counts[concept_idx] += 1
        self.last_updated_batch[concept_idx] = batch_id
        self.dirty_concept_indices.add(concept_idx)

    def bootstrap(
        self,
        centroid_embeddings: np.ndarray,
        *,
        chunk_counts: np.ndarray,
        batch_id: int,
    ) -> list[int]:
        return self._append_concepts_internal(
            centroid_embeddings, chunk_counts=chunk_counts, batch_id=batch_id
        )

    def append_concepts(
        self,
        centroids: np.ndarray,
        *,
        chunk_counts: list[int] | np.ndarray,
        batch_id: int,
    ) -> list[int]:
        counts = np.asarray(chunk_counts, dtype=np.int64)
        return self._append_concepts_internal(
            centroids, chunk_counts=counts, batch_id=batch_id
        )

    def _append_concepts_internal(
        self,
        centroids: np.ndarray,
        *,
        chunk_counts: np.ndarray,
        batch_id: int,
    ) -> list[int]:
        if len(centroids) == 0:
            return []

        n_new = len(centroids)
        dim = centroids.shape[1]
        if self.embeddings.size == 0:
            self.embeddings = np.asarray(centroids, dtype=np.float32)
        else:
            if dim != self.embeddings.shape[1]:
                raise ValueError("Centroid dimension mismatch")
            self.embeddings = np.vstack(
                [self.embeddings, np.asarray(centroids, dtype=np.float32)]
            )

        new_ids = list(range(self.next_concept_id, self.next_concept_id + n_new))
        self.next_concept_id += n_new
        self.concept_ids.extend(new_ids)

        self.chunk_counts = np.concatenate(
            [self.chunk_counts, chunk_counts.astype(np.int64)]
        )
        self.last_updated_batch = np.concatenate(
            [self.last_updated_batch, np.full(n_new, batch_id, dtype=np.int64)]
        )
        self.created_at.extend([_utc_now_iso()] * n_new)

        start_idx = len(self.concept_ids) - n_new
        self.dirty_concept_indices.update(range(start_idx, len(self.concept_ids)))
        return new_ids

    def push_orphans(
        self, orphan_embeddings: np.ndarray, orphan_chunk_ids: list[int] | np.ndarray
    ) -> None:
        ids = list(orphan_chunk_ids)
        for i, emb in enumerate(orphan_embeddings):
            self.orphan_embeddings.append(np.asarray(emb, dtype=np.float32))
            self.orphan_chunk_ids.append(int(ids[i]))

    def get_orphan_buffer(self) -> tuple[np.ndarray, list[int]]:
        if not self.orphan_embeddings:
            return np.empty((0, 0), dtype=np.float32), []
        return np.stack(self.orphan_embeddings), list(self.orphan_chunk_ids)

    def orphan_buffer_ready(self, settings: Settings) -> bool:
        threshold = settings.dictionary_k_min * settings.orphan_buffer_min_factor
        return len(self.orphan_embeddings) >= threshold

    def should_extract_orphans(
        self, settings: Settings, batch_orphan_count: int
    ) -> bool:
        """Full buffer at threshold, or partial flush so orphans get ACTIVATES this batch."""
        size = len(self.orphan_embeddings)
        if size == 0:
            return False
        if self.orphan_buffer_ready(settings):
            return True
        return batch_orphan_count > 0 and size >= 2

    def clear_orphan_buffer(self) -> None:
        self.orphan_embeddings.clear()
        self.orphan_chunk_ids.clear()

    def clear_dirty(self) -> None:
        self.dirty_concept_indices.clear()

    def sync_chunk_cursor_from_journal(self, journal: ChunkJournal) -> None:
        """Ensure next_chunk_id stays ahead of journaled chunk IDs after resume."""
        max_id = journal.max_chunk_id()
        if max_id is not None and max_id + 1 > self.next_chunk_id:
            self.next_chunk_id = max_id + 1

    def concept_records_for_neo4j(
        self, dirty: set[int] | None = None
    ) -> list[dict[str, Any]]:
        indices = sorted(dirty if dirty is not None else self.dirty_concept_indices)
        records: list[dict[str, Any]] = []
        for i in indices:
            records.append(
                {
                    "id": int(self.concept_ids[i]),
                    "chunk_count": int(self.chunk_counts[i]),
                    "last_updated_batch": int(self.last_updated_batch[i]),
                    "embedding": self.embeddings[i].tolist(),
                    "created_at": self.created_at[i],
                }
            )
        return records

    def save(self, state_dir: Path | None = None) -> None:
        directory = state_dir or data_state_dir()
        directory.mkdir(parents=True, exist_ok=True)

        np.savez_compressed(
            directory / "concepts.npz",
            embeddings=self.embeddings,
            chunk_counts=self.chunk_counts,
            last_updated_batch=self.last_updated_batch,
        )

        if self.orphan_embeddings:
            np.savez_compressed(
                directory / "orphan_buffer.npz",
                embeddings=np.stack(self.orphan_embeddings),
                chunk_ids=np.array(self.orphan_chunk_ids, dtype=np.int64),
            )
        else:
            orphan_path = directory / "orphan_buffer.npz"
            if orphan_path.exists():
                orphan_path.unlink()

        state = {
            "concept_ids": self.concept_ids,
            "created_at": self.created_at,
            "global_mean": self.global_mean.tolist() if self.global_mean.size else [],
            "total_embedded_chunks": self.total_embedded_chunks,
            "next_chunk_id": self.next_chunk_id,
            "next_concept_id": self.next_concept_id,
            "processed_topic_offset": self.processed_topic_offset,
            "embedding_dim": int(self.embeddings.shape[1])
            if self.embeddings.size
            else 0,
        }
        (directory / "state.json").write_text(
            json.dumps(state, indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, state_dir: Path | None = None) -> ConceptStore:
        directory = state_dir or data_state_dir()
        store = cls()
        state_path = directory / "state.json"
        if not state_path.exists():
            return store

        state = json.loads(state_path.read_text(encoding="utf-8"))
        store.concept_ids = [int(x) for x in state["concept_ids"]]
        store.created_at = list(state["created_at"])
        gm = state.get("global_mean", [])
        store.global_mean = np.array(gm, dtype=np.float64) if gm else np.empty(0)
        store.total_embedded_chunks = int(state["total_embedded_chunks"])
        store.next_chunk_id = int(state["next_chunk_id"])
        store.next_concept_id = int(state["next_concept_id"])
        store.processed_topic_offset = int(state["processed_topic_offset"])

        concepts_path = directory / "concepts.npz"
        if concepts_path.exists():
            data = np.load(concepts_path)
            store.embeddings = data["embeddings"].astype(np.float32)
            store.chunk_counts = data["chunk_counts"].astype(np.int64)
            store.last_updated_batch = data["last_updated_batch"].astype(np.int64)

        orphan_path = directory / "orphan_buffer.npz"
        if orphan_path.exists():
            data = np.load(orphan_path)
            embs = data["embeddings"]
            ids = data["chunk_ids"]
            store.orphan_embeddings = [embs[i] for i in range(len(embs))]
            store.orphan_chunk_ids = [int(ids[i]) for i in range(len(ids))]

        return store
