# v1 — Limitations (why v2 exists)

> While the **Topological Manifold** pipeline generates a mathematically rich topological skeleton, it requires holding the entire $`N \times D`$ embedding matrix in RAM and rebuilding the graph from scratch on new data.

| Limitation | Impact |
|------------|--------|
| **Full-matrix RAM** | Scales poorly beyond ~10k chunks; no streaming |
| **Static batch** | New documents require a full re-run |
| **Neo4j wipe-and-reload** | No incremental MERGE; downtime on every publish |
| **Frozen concepts** | No online EMA; manifold drift across time is ignored |
| **No batch metrics** | No `metrics.csv`, smoke tests, or E2E invariants |

The **Latent Semantic Attractor Graph** ([v2 manual](../v2-latent-semantic-attractor-graph/README.md) · [`v2_orchestrator/`](../../v2_orchestrator/)) addresses each of these: disk journal, resumable `ConceptStore`, MERGE upserts, and living attractors.

See also: [ADR 001 — Streaming migration](../architecture-decisions/001-streaming-migration.md) · [Root README — Two Architectures](../../README.md#two-architectures)
