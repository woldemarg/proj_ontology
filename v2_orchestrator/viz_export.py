"""Materialize sphere plot artifacts for v1_single_pass/visualisation/plot_ontology_sphere.py."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from v2_orchestrator.chunk_journal import ChunkJournal
from v2_orchestrator.paths import resolve_project_root, visualisation_artifacts_dir
from v2_orchestrator.storage import ConceptStore

_DEFAULT_HTML = visualisation_artifacts_dir().parent / "ontology_sphere.html"


def materialize(store: ConceptStore, journal: ChunkJournal) -> None:
    output_dir = visualisation_artifacts_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    chunks, embeddings = journal.materialize_numpy_cache()
    if chunks:
        with (output_dir / "chunks.json").open("w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2)
        np.save(output_dir / "embeddings.npy", embeddings)

    if len(store.embeddings) == 0:
        return

    np.save(output_dir / "concept_embeddings.npy", store.embeddings)

    concept_id_to_viz: dict[int, int] = {
        cid: idx for idx, cid in enumerate(store.concept_ids)
    }
    chunk_id_to_viz: dict[int, int] = {
        int(chunk["id"]): idx for idx, chunk in enumerate(chunks)
    }

    concepts_json: list[dict[str, Any]] = []
    for idx, cid in enumerate(store.concept_ids):
        concepts_json.append(
            {
                "id": idx,
                "global_id": int(cid),
                "level": 0,
                "density": int(store.chunk_counts[idx]),  # viz schema for plot_ontology_sphere
                "name": f"Concept {cid}",
            }
        )

    activations = journal.load_activations()
    viz_activations: list[dict[str, Any]] = []
    for edge in activations:
        chunk_viz = chunk_id_to_viz.get(int(edge["chunk_id"]))
        concept_viz = concept_id_to_viz.get(int(edge["concept_id"]))
        if chunk_viz is None or concept_viz is None:
            continue
        viz_activations.append(
            {
                "chunk_id": chunk_viz,
                "concept_id": concept_viz,
                "weight": edge["weight"],
            }
        )

    with (output_dir / "concepts.json").open("w", encoding="utf-8") as f:
        json.dump(concepts_json, f, indent=2)
    with (output_dir / "activations.json").open("w", encoding="utf-8") as f:
        json.dump(viz_activations, f, indent=2)

    dim = int(store.embeddings.shape[1]) if store.embeddings.size else 0
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "num_chunks": len(chunks),
        "embedding_dim": dim,
        "coordinate_space": "ambient",
        "num_concepts_l0": len(store.concept_ids),
        "num_activations": len(viz_activations),
    }
    with (output_dir / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Viz artifacts materialized → {output_dir.resolve()}")


def render_sphere_plot(
    output_path: Path | None = None,
    *,
    draw_edges: bool | None = None,
) -> Path:
    """Render prosphera sphere HTML from v2_orchestrator visualization artifacts."""
    art = visualisation_artifacts_dir()
    required = ("concept_embeddings.npy", "concepts.json", "activations.json", "chunks.json", "embeddings.npy")
    missing = [name for name in required if not (art / name).is_file()]
    if missing:
        raise FileNotFoundError(
            "Missing visualisation artifacts — run v2_orchestrator with KEEP_VISUAL_ARTIFACTS=true "
            f"or call materialize() first. Missing: {', '.join(missing)}"
        )

    out = output_path or _DEFAULT_HTML
    plot_script = (
        resolve_project_root() / "v1_single_pass" / "visualisation" / "plot_ontology_sphere.py"
    )
    cmd = [
        sys.executable,
        str(plot_script),
        "--chunks",
        str(art / "chunks.json"),
        "--embeddings",
        str(art / "embeddings.npy"),
        "--artifacts",
        str(art),
        "-o",
        str(out),
    ]
    if draw_edges is True:
        cmd.append("--draw-edges")
    elif draw_edges is False:
        cmd.append("--no-draw-edges")

    subprocess.run(cmd, check=True)
    print(f"Sphere plot saved → {out.resolve()}")
    return out
