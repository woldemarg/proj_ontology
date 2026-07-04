"""Ingestion, embedding, and ontology extraction pipeline."""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
import wikipedia
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from sklearn.decomposition import MiniBatchDictionaryLearning
from sklearn.metrics.pairwise import cosine_similarity

from ontology.paths import data_cache_dir, model_cache_dir
from ontology.settings import Settings

WIKIPEDIA_TOPICS = [
    "Quantum computing",
    "Philosophy of mind",
    "Neuroscience",
    "Artificial neural network",
    "Linguistics",
    "Epistemology",
    "Evolutionary biology",
    "Complex system",
]


def article_neo4j_label(title: str) -> str:
    """Sanitize an article title into a valid secondary Neo4j node label."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_") or "Unknown"
    if slug[0].isdigit():
        slug = f"A_{slug}"
    return f"Article_{slug}"[:63]


def enrich_chunk_article_labels(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for chunk in chunks:
        article = chunk.get("article") or chunk["source"]
        chunk["article"] = article
        chunk["article_label"] = article_neo4j_label(article)
    return chunks


def _docs_fingerprint(docs: list[dict[str, Any]]) -> str:
    titles = "|".join(doc["title"] for doc in docs)
    return hashlib.md5(titles.encode("utf-8")).hexdigest()


def _save_docs_cache(docs: list[dict[str, Any]], settings: Settings) -> Path:
    path = data_cache_dir() / settings.docs_cache_file
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(docs, file)
    return path


def _load_docs_cache(settings: Settings) -> list[dict[str, Any]] | None:
    path = data_cache_dir() / settings.docs_cache_file
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _save_embeddings_cache(
    docs: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    embeddings: np.ndarray,
    settings: Settings,
) -> None:
    cache_dir = data_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "model": settings.embedding_model,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "docs_fingerprint": _docs_fingerprint(docs),
        "num_chunks": len(chunks),
        "embedding_dim": int(embeddings.shape[1]),
    }

    with (cache_dir / settings.chunks_cache_file).open("w", encoding="utf-8") as file:
        json.dump(chunks, file)
    np.save(cache_dir / settings.embeddings_cache_file, embeddings)
    with (cache_dir / settings.embed_manifest_file).open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2)


def _load_embeddings_cache(
    docs: list[dict[str, Any]], settings: Settings
) -> tuple[list[dict[str, Any]], np.ndarray] | None:
    cache_dir = data_cache_dir()
    chunks_path = cache_dir / settings.chunks_cache_file
    embeddings_path = cache_dir / settings.embeddings_cache_file
    manifest_path = cache_dir / settings.embed_manifest_file

    if not (
        chunks_path.exists() and embeddings_path.exists() and manifest_path.exists()
    ):
        return None

    with manifest_path.open(encoding="utf-8") as file:
        manifest = json.load(file)

    expected_manifest = {
        "model": settings.embedding_model,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "docs_fingerprint": _docs_fingerprint(docs),
    }
    for key, value in expected_manifest.items():
        if manifest.get(key) != value:
            return None

    with chunks_path.open(encoding="utf-8") as file:
        chunks = json.load(file)
    embeddings = np.load(embeddings_path)

    if len(chunks) != manifest.get("num_chunks") or embeddings.shape[0] != len(chunks):
        return None

    return chunks, embeddings


def load_or_fetch_articles(
    settings: Settings, force_refresh: bool = False
) -> list[dict[str, Any]]:
    if not force_refresh:
        cached_docs = _load_docs_cache(settings)
        if cached_docs:
            cache_path = data_cache_dir() / settings.docs_cache_file
            print(f"Loading cached articles from {cache_path}")
            print(f" -> Loaded {len(cached_docs)} articles from cache.")
            return cached_docs

    docs = fetch_wikipedia_articles(settings)
    if docs:
        cache_path = _save_docs_cache(docs, settings)
        print(f"Saved articles to {cache_path}")
    return docs


def load_or_embed_chunks(
    docs: list[dict[str, Any]],
    settings: Settings,
    force_refresh: bool = False,
) -> tuple[list[dict[str, Any]], np.ndarray]:
    if not force_refresh:
        cached = _load_embeddings_cache(docs, settings)
        if cached is not None:
            chunks, embeddings = cached
            chunks = enrich_chunk_article_labels(chunks)
            print(f"Loading cached chunks/embeddings from {data_cache_dir()}")
            print(
                f" -> Loaded {len(chunks)} chunks, embeddings shape {embeddings.shape}"
            )
            return chunks, embeddings

    chunks = chunk_documents(docs, settings)
    embeddings = embed_chunks(chunks, settings)
    _save_embeddings_cache(docs, chunks, embeddings, settings)
    print(f"Saved chunks/embeddings to {data_cache_dir()}")
    return chunks, embeddings


def fetch_wikipedia_articles(settings: Settings) -> list[dict[str, Any]]:
    print("Fetching Wikipedia articles...")
    wikipedia.set_user_agent(settings.wikipedia_user_agent)

    docs: list[dict[str, Any]] = []
    for topic in WIKIPEDIA_TOPICS:
        for attempt in range(settings.wikipedia_max_retries):
            try:
                if attempt > 0 or docs:
                    delay = settings.wikipedia_request_delay_seconds * (2**attempt)
                    time.sleep(delay)
                page = wikipedia.page(topic, auto_suggest=False)
                docs.append({"title": page.title, "content": page.content})
                print(f" -> Fetched: {page.title}")
                break
            except Exception as exc:
                if attempt == settings.wikipedia_max_retries - 1:
                    print(f" -> Failed to fetch {topic}: {exc}")
                else:
                    print(
                        f" -> Retry {attempt + 1}/{settings.wikipedia_max_retries} "
                        f"for {topic}: {exc}"
                    )
    return docs


def chunk_documents(
    docs: list[dict[str, Any]], settings: Settings
) -> list[dict[str, Any]]:
    print("\nChunking documents...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
    )

    chunks: list[dict[str, Any]] = []
    chunk_id = 0
    for doc in docs:
        for split in text_splitter.split_text(doc["content"]):
            chunks.append(
                {
                    "id": chunk_id,
                    "text": split,
                    "source": doc["title"],
                    "article": doc["title"],
                    "article_label": article_neo4j_label(doc["title"]),
                }
            )
            chunk_id += 1

    print(f"Generated {len(chunks)} total chunks.")
    return enrich_chunk_article_labels(chunks)


def embed_chunks(chunks: list[dict[str, Any]], settings: Settings) -> np.ndarray:
    print("\nLoading local embedding model...")
    cache_dir = model_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    print(f"Model cache: {cache_dir}")

    model = SentenceTransformer(
        settings.embedding_model,
        cache_folder=str(cache_dir),
    )
    texts = [chunk["text"] for chunk in chunks]
    print(f"Embedding chunks (batch_size={settings.embed_batch_size})...")
    embeddings = model.encode(
        texts,
        batch_size=settings.embed_batch_size,
        show_progress_bar=True,
    )

    mean_vector = np.mean(embeddings, axis=0)
    centered_embeddings = embeddings - mean_vector
    norms = np.linalg.norm(centered_embeddings, axis=1, keepdims=True)
    return centered_embeddings / norms


def build_ontology_graph(
    embeddings: np.ndarray,
    settings: Settings,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Extract concept nodes and relationships from chunk embeddings."""
    print("\n--- Extracting ontology graph ---")

    concepts_per_chunk = settings.concepts_per_chunk
    print(
        f"Optimizing concept count (K) via OMP "
        f"(target exactly {concepts_per_chunk} concepts per chunk)..."
    )

    best_coefficients = None
    best_dictionary = None
    previous_error = float("inf")
    selected_k = settings.dictionary_k_min
    matrix_norm_sq = np.linalg.norm(embeddings, "fro") ** 2

    for k in range(
        settings.dictionary_k_min,
        settings.max_concept_count + 1,
        settings.dictionary_k_step,
    ):
        dictionary_learner = MiniBatchDictionaryLearning(
            n_components=k,
            transform_algorithm="omp",
            transform_n_nonzero_coefs=concepts_per_chunk,
            batch_size=settings.dictionary_batch_size,
            random_state=settings.random_seed,
        )
        coefficients = dictionary_learner.fit_transform(embeddings)
        dictionary = dictionary_learner.components_

        reconstruction = coefficients @ dictionary
        reconstruction_error = (
            np.linalg.norm(embeddings - reconstruction, "fro") ** 2 / matrix_norm_sq
        )

        concept_usage = np.sum(np.abs(coefficients) > 1e-5, axis=0)
        dead_concepts = int(np.sum(concept_usage == 0))
        dead_ratio = dead_concepts / k
        improvement = previous_error - reconstruction_error

        print(
            f" -> K={k:03d} | Error: {reconstruction_error:.4f} | "
            f"Dead Nodes: {dead_concepts} ({dead_ratio * 100:.1f}%) | "
            f"Improvement: {improvement if previous_error != float('inf') else 0:.4f}"
        )

        if dead_ratio > settings.max_dead_concept_ratio:
            if best_coefficients is not None:
                print(
                    f"Stopping: Hard dead-node limit "
                    f"({settings.max_dead_concept_ratio:.0%}) exceeded. "
                    f"Reverting to K={selected_k}"
                )
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
                f"Stopping: Improvement ({improvement:.4f}) failed to clear "
                f"dynamic threshold ({dynamic_tolerance:.4f}) adjusted for dead nodes."
            )
            break

        best_coefficients = coefficients
        best_dictionary = dictionary
        selected_k = k
        previous_error = reconstruction_error

    if best_coefficients is None:
        raise RuntimeError(
            f"No viable dictionary found: all K values exceeded the "
            f"{settings.max_dead_concept_ratio:.0%} dead-node limit. "
            "Try lowering CONCEPTS_PER_CHUNK or RECONSTRUCTION_ERROR_TOLERANCE."
        )

    coefficients_abs = np.abs(best_coefficients)

    concept_usage = np.sum(coefficients_abs > 1e-5, axis=0)
    active_concept_indices = np.where(concept_usage > 0)[0]
    orphan_count = selected_k - len(active_concept_indices)
    if orphan_count:
        print(f"Pruning {orphan_count} orphan concepts before final assignment.")

    coefficients_abs = coefficients_abs[:, active_concept_indices]
    dictionary = best_dictionary[active_concept_indices, :]
    concept_count = len(active_concept_indices)
    chunk_densities = np.sum(coefficients_abs > 1e-5, axis=0)

    print("Extracting pure dictionary atoms as concept embeddings...")
    concept_embeddings = dictionary
    norms = np.linalg.norm(concept_embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    concept_embeddings = concept_embeddings / norms

    print(
        f"Assigning chunks to top-{concepts_per_chunk} concept attractors (|weight|)..."
    )
    activation_edges: list[dict[str, Any]] = []
    assigned_chunks: set[int] = set()
    for chunk_index in range(len(embeddings)):
        top_concept_indices = np.argsort(coefficients_abs[chunk_index])[
            -concepts_per_chunk:
        ]
        for concept_index in top_concept_indices:
            weight = float(coefficients_abs[chunk_index, concept_index])
            if weight > 1e-5:
                activation_edges.append(
                    {
                        "chunk_id": chunk_index,
                        "concept_id": int(concept_index),
                        "weight": weight,
                    }
                )
                assigned_chunks.add(chunk_index)

    print(
        f"Sanity check: {len(assigned_chunks)} of {len(embeddings)} chunks connected."
    )

    concept_nodes = [
        {
            "id": index,
            "level": 0,
            "density": int(chunk_densities[index]),
            "name": f"Latent Concept {active_concept_indices[index]}",
        }
        for index in range(concept_count)
    ]

    print("Inducing lateral concept graph topology (RELATED_TO)...")
    similarity_matrix = cosine_similarity(concept_embeddings)
    np.fill_diagonal(similarity_matrix, -1)

    seen_edges: set[tuple[int, int]] = set()
    similarity_edges: list[dict[str, Any]] = []
    for source_index in range(concept_count):
        peer_indices = np.argsort(similarity_matrix[source_index])[
            -settings.related_to_peer_count :
        ]
        for target_index in peer_indices:
            weight = similarity_matrix[source_index, target_index]
            if weight > settings.related_to_min_weight:
                edge_key = (
                    min(int(source_index), int(target_index)),
                    max(int(source_index), int(target_index)),
                )
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    similarity_edges.append(
                        {
                            "source": edge_key[0],
                            "target": edge_key[1],
                            "weight": float(weight),
                        }
                    )

    print(
        f"RELATED_TO: top-{settings.related_to_peer_count} k-NN per concept -> "
        f"{len(similarity_edges)} unique edges"
    )

    print("Building taxonomic hierarchy (SUPER_CONCEPT_OF) via community detection...")
    super_concept_nodes: list[dict[str, Any]] = []
    hierarchy_edges: list[dict[str, Any]] = []

    if concept_count > 1:
        concept_graph = nx.Graph()
        for edge in similarity_edges:
            concept_graph.add_edge(
                edge["source"], edge["target"], weight=edge["weight"]
            )
        for index in range(concept_count):
            if not concept_graph.has_node(index):
                concept_graph.add_node(index)

        communities = nx.community.louvain_communities(
            concept_graph,
            weight="weight",
            resolution=settings.louvain_resolution,
            seed=settings.random_seed,
        )
        for community_index, community in enumerate(communities):
            super_concept_id = concept_count + community_index
            super_concept_nodes.append(
                {
                    "id": super_concept_id,
                    "level": 1,
                    "density": 0,
                    "name": f"Super Concept {super_concept_id}",
                }
            )
            for child_id in community:
                hierarchy_edges.append(
                    {"source": super_concept_id, "target": int(child_id)}
                )

    all_concept_nodes = concept_nodes + super_concept_nodes
    return activation_edges, all_concept_nodes, similarity_edges, hierarchy_edges
