"""Batched Wikipedia ingest — returns raw embeddings (no centering)."""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import wikipedia
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from v2_orchestrator.paths import model_cache_dir
from v2_orchestrator.settings import Settings

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from corpus.hf_hub import sentence_transformer_token_kwargs
from corpus.wikipedia_topics import WIKIPEDIA_TOPICS  # noqa: E402


def article_neo4j_label(title: str) -> str:
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


def fetch_topics_batch(settings: Settings, topic_offset: int) -> list[dict[str, Any]]:
    """Fetch the next slice of Wikipedia topics for streaming batches."""
    end = min(topic_offset + settings.articles_per_batch, len(WIKIPEDIA_TOPICS))
    if topic_offset >= len(WIKIPEDIA_TOPICS):
        return []

    wikipedia.set_user_agent(settings.wikipedia_user_agent)
    docs: list[dict[str, Any]] = []
    for topic in WIKIPEDIA_TOPICS[topic_offset:end]:
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
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
    )
    chunks: list[dict[str, Any]] = []
    for doc in docs:
        for split in text_splitter.split_text(doc["content"]):
            chunks.append(
                {
                    "text": split,
                    "source": doc["title"],
                    "article": doc["title"],
                }
            )
    return enrich_chunk_article_labels(chunks)


def embed_chunks_raw(chunks: list[dict[str, Any]], settings: Settings) -> np.ndarray:
    """Return raw model embeddings — no mean subtraction or L2 normalization."""
    cache_dir = model_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    model = SentenceTransformer(
        settings.embedding_model,
        cache_folder=str(cache_dir),
        **sentence_transformer_token_kwargs(settings.hf_token),
    )
    texts = [chunk["text"] for chunk in chunks]
    print(f"Embedding {len(texts)} chunks (batch_size={settings.embed_batch_size})...")
    return np.asarray(
        model.encode(
            texts,
            batch_size=settings.embed_batch_size,
            show_progress_bar=len(texts) > 16,
        ),
        dtype=np.float32,
    )


def ingest_batch(
    settings: Settings, topic_offset: int
) -> tuple[list[dict[str, Any]], np.ndarray]:
    """Fetch topics, chunk, embed; returns (chunks, X_raw) without global IDs."""
    docs = fetch_topics_batch(settings, topic_offset)
    if not docs:
        return [], np.empty((0, 0), dtype=np.float32)
    chunks = chunk_documents(docs, settings)
    if not chunks:
        return [], np.empty((0, 0), dtype=np.float32)
    x_raw = embed_chunks_raw(chunks, settings)
    print(f"Ingested {len(chunks)} chunks from {len(docs)} articles.")
    return chunks, x_raw
