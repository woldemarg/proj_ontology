# Documentation

**New here?** [Repository README](../README.md) — overview, product comparison, quick start, and the canonical RAG query.

Long-form docs live here, organized by version. Runnable code is in `v1_single_pass/` and `v2_orchestrator/`; package READMEs are thin entry points that link back here.

---

## How docs are organized

| Layer | Where | What belongs there |
|-------|-------|-------------------|
| **Onboarding** | [Root README](../README.md) | Product comparison, quick starts, mental model, full `rag_subgraph.cypher` |
| **Index** | This file | Navigation — one link per topic, no duplicated runbooks |
| **Product hub** | `v1-topological-manifold/`, `v2-latent-semantic-attractor-graph/` | Intro + doc map + pipeline diagram |
| **Topic docs** | Files under each hub | Single canonical home per subject (math, ops, tuning, …) |
| **Package stub** | `v1_single_pass/README.md`, `v2_orchestrator/README.md` | Entry command + links to runbook |

---

## Products

| Version | Product | Manual | Code | Neo4j DB |
|---------|---------|--------|------|----------|
| **v1** | Topological Manifold | [v1-topological-manifold/](v1-topological-manifold/README.md) | [`v1_single_pass/`](../v1_single_pass/) | `ontologyv1` |
| **v2** | Latent Semantic Attractor Graph | [v2-latent-semantic-attractor-graph/](v2-latent-semantic-attractor-graph/README.md) | [`v2_orchestrator/`](../v2_orchestrator/) | `ontologyv2` |

---

## Quick navigation

| I need to… | Read |
|------------|------|
| Choose v1 vs v2 | [Root README — Two architectures](../README.md#two-architectures) |
| Run v1 | [v1 operations](v1-topological-manifold/operations.md#run-locally) |
| Run v2 | [v2 operations](v2-latent-semantic-attractor-graph/operations.md#run-locally) |
| v1 math (5-stage pipeline) | [mathematical-foundations.md](v1-topological-manifold/mathematical-foundations.md) |
| v1 Neo4j schema | [graph-schema.md](v1-topological-manifold/graph-schema.md) |
| v2 data flow | [data-flow.md](v2-latent-semantic-attractor-graph/data-flow.md) |
| v2 concept inertia | [concept-inertia.md](v2-latent-semantic-attractor-graph/concept-inertia.md) |
| v2 tuning (`.env`) | [configuration.md](v2-latent-semantic-attractor-graph/configuration.md) |
| Why v2 exists | [limitations.md](v1-topological-manifold/limitations.md) |
| RAG Cypher | [Root README — RAG](../README.md#rag--graph-traversal) · [query files](cypher/queries/README.md) |
| Contribute / verify | [CONTRIBUTING.md](../CONTRIBUTING.md) |

---

## Repository layout

```
proj_ontology/
  README.md
  CONTRIBUTING.md
  CHANGELOG.md
  requirements.txt
  .env.sample
  docs/
    README.md                          # this index
    v1-topological-manifold/           # v1 hub + topic docs
    v2-latent-semantic-attractor-graph/  # v2 hub + topic docs
    architecture-decisions/            # ADRs
    assets/                            # committed sphere screenshots (v1 + v2)
    cypher/queries/                    # shared .cypher files
  corpus/                              # 40-topic Wikipedia list (v1: 8, v2: 40)
  v1_single_pass/                      # v1 code
  v2_orchestrator/                     # v2 code
  models/                              # embedding cache (runtime)
```

---

## Shared resources

- **Requirements:** [`requirements.txt`](../requirements.txt)
- **Embedding cache:** [`models/`](../models/)
- **Wikipedia corpus:** [`corpus/wikipedia_topics.py`](../corpus/wikipedia_topics.py) — **40**-topic master list; v1 POC uses first **8**, v2 MVP ingests all **40**
- **Screenshots:** [`assets/`](assets/) — committed sphere samples from completed runs
  - [`mvp-topological-manifold-graph-sphere.png`](assets/mvp-topological-manifold-graph-sphere.png) — v1 POC (8 articles)
  - [`mvp-latent-semantic-attractor-graph-sphere.png`](assets/mvp-latent-semantic-attractor-graph-sphere.png) — v2 MVP (40 articles)
- **Interactive viz** (generated locally, not under `docs/assets/`): sphere HTML in each package's `data/visualisation/` — [root README — Explore the graph interactively](../README.md#explore-the-graph-interactively)
- **Math in docs:** block equations use GitHub ` ```math ` fences (preserves `\|` and `\frac`); inline LaTeX with backslashes uses `` $`...`$ ``. In Cursor/VS Code, enable **Markdown › Math: Enabled** for local preview.
