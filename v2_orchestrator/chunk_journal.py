"""Append-only chunk journal on disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from v2_orchestrator.paths import data_cache_dir


class ChunkJournal:
    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = cache_dir or data_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.chunks_path = self.cache_dir / "chunks.jsonl"
        self.activations_path = self.cache_dir / "activations.jsonl"
        self.embeddings_path = self.cache_dir / "embeddings.mmap"

    def append_batch(
        self,
        chunks: list[dict[str, Any]],
        x_centered: np.ndarray,
        activations: list[dict[str, Any]],
    ) -> None:
        if len(chunks) != len(x_centered):
            raise ValueError("chunks and x_centered row count mismatch")

        with self.chunks_path.open("a", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

        self._append_embeddings(x_centered)

        with self.activations_path.open("a", encoding="utf-8") as f:
            for edge in activations:
                f.write(json.dumps(edge) + "\n")

    def _append_embeddings(self, x_centered: np.ndarray) -> None:
        n_new, dim = x_centered.shape
        if n_new == 0:
            return

        existing = self.load_embeddings()
        if existing.size:
            combined = np.vstack([existing, x_centered.astype(np.float32)])
        else:
            combined = x_centered.astype(np.float32)

        if self.embeddings_path.exists():
            self.embeddings_path.unlink()

        mmap = np.memmap(
            self.embeddings_path,
            dtype=np.float32,
            mode="w+",
            shape=combined.shape,
        )
        mmap[:] = combined
        mmap.flush()
        del mmap

        meta_path = self.cache_dir / "embeddings_meta.json"
        meta_path.write_text(
            json.dumps({"rows": int(combined.shape[0]), "dim": int(dim)}),
            encoding="utf-8",
        )

    def _memmap_shape(self) -> tuple[int, int]:
        meta_path = self.cache_dir / "embeddings_meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            return int(meta["rows"]), int(meta["dim"])
        n_chunks = self._line_count(self.chunks_path)
        if n_chunks == 0:
            return 0, 0
        file_bytes = self.embeddings_path.stat().st_size
        dim = file_bytes // (n_chunks * 4)
        return n_chunks, dim

    @staticmethod
    def _line_count(path: Path) -> int:
        if not path.exists():
            return 0
        with path.open(encoding="utf-8") as f:
            return sum(1 for _ in f)

    def load_chunks(self) -> list[dict[str, Any]]:
        if not self.chunks_path.exists():
            return []
        chunks: list[dict[str, Any]] = []
        with self.chunks_path.open(encoding="utf-8") as f:
            for line in f:
                chunks.append(json.loads(line))
        return chunks

    def load_embeddings(self) -> np.ndarray:
        if not self.embeddings_path.exists():
            return np.empty((0, 0), dtype=np.float32)
        rows, dim = self._memmap_shape()
        if rows == 0:
            return np.empty((0, 0), dtype=np.float32)
        mmap = np.memmap(
            self.embeddings_path, dtype=np.float32, mode="r", shape=(rows, dim)
        )
        return np.array(mmap)

    def load_activations(self) -> list[dict[str, Any]]:
        if not self.activations_path.exists():
            return []
        edges: list[dict[str, Any]] = []
        with self.activations_path.open(encoding="utf-8") as f:
            for line in f:
                edges.append(json.loads(line))
        return edges

    def max_chunk_id(self) -> int | None:
        if not self.chunks_path.exists():
            return None
        max_id: int | None = None
        with self.chunks_path.open(encoding="utf-8") as f:
            for line in f:
                chunk_id = int(json.loads(line)["id"])
                if max_id is None or chunk_id > max_id:
                    max_id = chunk_id
        return max_id

    def row_count(self) -> int:
        return self._line_count(self.chunks_path)

    def materialize_numpy_cache(self) -> tuple[list[dict[str, Any]], np.ndarray]:
        return self.load_chunks(), self.load_embeddings()
