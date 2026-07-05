# ADR 001: Streaming migration (v1 → v2)

| | |
|---|---|
| **Status** | Accepted — implemented |
| **Date** | July 2026 |
| **v1 (research)** | [`v1_single_pass/`](../../v1_single_pass/) · [`docs/v1-topological-manifold/`](../v1-topological-manifold/README.md) |
| **v2 (production)** | [`v2_orchestrator/`](../../v2_orchestrator/) · [`docs/v2-latent-semantic-attractor-graph/`](../v2-latent-semantic-attractor-graph/README.md) |

## Context

**v1 — Topological Manifold** proved that a continuous semantic manifold can be discretized into a traversable graph without predefined categories. It runs as a **single static batch**: full embedding matrix in RAM, frozen OMP concepts, Louvain L1 hierarchy, Neo4j wipe-and-reload.

That model breaks down for production: RAM scales with corpus size, new documents require a full rebuild, and concepts cannot drift with incoming text.

## Decision

Ship **v2 — Latent Semantic Attractor Graph** as a separate package (`v2_orchestrator/`) with:

- **Streaming batches** — resumable ingest via `processed_topic_offset`
- **Living centroids** — OMP seeds + EMA updates with concept inertia
- **Disk journal** — `chunks.jsonl`, `activations.jsonl`, `embeddings.mmap`, `ConceptStore` on disk
- **MERGE-only Neo4j** — incremental upserts; no graph wipe per batch
- **Mutual k-NN `RELATED_TO`** — lateral topology tuned for RAG traversal
- **Observability** — `metrics.csv`, smoke and E2E verification tests

v1 remains unchanged as the research reference implementation.

## Consequences

| Area | v1 | v2 |
|------|----|----|
| Memory | Full $`N \times D`$ matrix | Batch-sized + disk journal |
| Concepts | Frozen OMP atoms | EMA attractors (`chunk_count`) |
| Hierarchy | Louvain L1 (`SUPER_CONCEPT_OF`) | L0 only |
| Neo4j writes | Drop + bulk CREATE | MERGE upserts |
| `RELATED_TO` | Top-k cosine | Mutual k-NN; stale edges may persist (MERGE-only trade-off) |
| Sphere viz | Native v1 artifacts | `viz_export` → shared `plot_ontology_sphere.py` |

## Out of scope (by design)

- Louvain / `SUPER_CONCEPT_OF` in v2
- Batch-local-only centering without running `global_mean`
- Static assignment thresholds (v2 uses adaptive percentile band)
- `RELATED_TO` DELETE on peer change (accepted for traversal stability)

## References

- v1 limitations: [limitations.md](../v1-topological-manifold/limitations.md)
- v2 data flow: [data-flow.md](../v2-latent-semantic-attractor-graph/data-flow.md)
- Product comparison: [root README — Two architectures](../../README.md#two-architectures)
