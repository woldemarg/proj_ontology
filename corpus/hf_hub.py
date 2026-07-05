"""Hugging Face Hub auth for SentenceTransformer downloads."""

from __future__ import annotations

import os


def apply_hf_token(token: str) -> None:
    """Set HF env vars so huggingface_hub uses authenticated requests."""
    if not token:
        return
    os.environ.setdefault("HF_TOKEN", token)
    os.environ.setdefault("HUGGING_FACE_HUB_TOKEN", token)


def sentence_transformer_token_kwargs(hf_token: str) -> dict[str, str]:
    if hf_token:
        return {"token": hf_token}
    return {}
