"""Plot chunks and L0 concepts on a prosphera sphere.

Run script/main.py with KEEP_VISUAL_ARTIFACTS=true first.

Usage:
    python script/visualisation/plot_ontology_sphere.py
    python script/visualisation/plot_ontology_sphere.py -o data/visualisation/ontology_sphere.html
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR.parent))

from ontology.paths import data_cache_dir, visualisation_artifacts_dir  # noqa: E402
from ontology.settings import load_settings  # noqa: E402
from visualisation.projector import OntologyProjector  # noqa: E402

_REQUIRED_ARTIFACTS = ("concept_embeddings.npy", "concepts.json", "activations.json")


def _resolve_draw_edges(
    settings,
    num_chunks: int,
    *,
    force_on: bool,
    force_off: bool,
) -> bool:
    if force_off:
        return False
    if force_on:
        return True
    if num_chunks >= settings.edge_auto_disable_chunk_threshold:
        print(
            f"Skipping ACTIVATES edges: {num_chunks} chunks >= "
            f"{settings.edge_auto_disable_chunk_threshold}. "
            "Set DRAW_EDGES=true or pass --draw-edges to force."
        )
        return False
    return settings.draw_edges


def _build_hover_texts(
    chunks: list[dict], concepts: list[dict]
) -> tuple[list[str], list[str], list[str]]:
    labels = [chunk["source"] for chunk in chunks]
    chunk_hovers = []
    for chunk in chunks:
        text = chunk["text"].replace("\n", " ").strip()
        preview = text[:120] + ("..." if len(text) > 120 else "")
        chunk_hovers.append(
            f"<b>📄 Source Document:</b> {chunk['source']}<br>"
            f"<b>🆔 Chunk ID:</b> #{chunk['id']}<br>"
            f"<b>🔍 Text Content:</b><br><i>{preview}</i>"
        )
    concept_hovers = [
        f"<b>🧠 Latent Concept Anchor</b><br>"
        f"<b>🆔 Internal Index:</b> {concept['id']}<br>"
        f"<b>📊 Topological Density:</b> Pulls {concept['density']} document chunks"
        for concept in concepts
    ]
    return labels, chunk_hovers, concept_hovers


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot ontology sphere (chunks + L0).")
    settings = load_settings()
    cache = data_cache_dir()

    parser.add_argument(
        "--embeddings",
        type=Path,
        default=cache / settings.embeddings_cache_file,
    )
    parser.add_argument(
        "--chunks", type=Path, default=cache / settings.chunks_cache_file
    )
    parser.add_argument("--artifacts", type=Path, default=visualisation_artifacts_dir())
    parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument("--random-state", type=int, default=1234)
    edges = parser.add_mutually_exclusive_group()
    edges.add_argument("--draw-edges", action="store_true")
    edges.add_argument("--no-draw-edges", action="store_true")
    args = parser.parse_args()

    missing = [
        args.artifacts / name
        for name in _REQUIRED_ARTIFACTS
        if not (args.artifacts / name).exists()
    ]
    if missing:
        raise FileNotFoundError(
            "Missing visualisation artifacts — run script/main.py with "
            "KEEP_VISUAL_ARTIFACTS=true first:\n  "
            + "\n  ".join(str(path) for path in missing)
        )

    chunk_embeddings = np.load(args.embeddings)
    concept_embeddings = np.load(args.artifacts / "concept_embeddings.npy")
    with args.chunks.open(encoding="utf-8") as f:
        chunks = json.load(f)
    with (args.artifacts / "concepts.json").open(encoding="utf-8") as f:
        concepts = json.load(f)
    with (args.artifacts / "activations.json").open(encoding="utf-8") as f:
        activations = json.load(f)

    if len(chunks) != chunk_embeddings.shape[0]:
        raise ValueError(
            f"Chunk count ({len(chunks)}) != embedding rows ({chunk_embeddings.shape[0]})"
        )
    if len(concepts) != concept_embeddings.shape[0]:
        raise ValueError("Concept embeddings and metadata row counts differ.")

    labels, chunk_hovers, concept_hovers = _build_hover_texts(chunks, concepts)

    OntologyProjector(random_state=args.random_state).project_ontology(
        chunk_embeddings,
        concept_embeddings,
        activations,
        chunk_labels=labels,
        chunk_hovertext=chunk_hovers,
        concept_hovertext=concept_hovers,
        draw_edges=_resolve_draw_edges(
            settings,
            len(chunks),
            force_on=args.draw_edges,
            force_off=args.no_draw_edges,
        ),
        output_path=args.output,
    )
    if args.output:
        print(f"Saved → {args.output.resolve()}")


if __name__ == "__main__":
    main()
