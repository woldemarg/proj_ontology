# v1 — Operations & codebase

## Prerequisites

Python 3.10+, Neo4j (Bolt), repo-root [`.env`](../../.env.sample).

## Run locally

```cypher
CREATE DATABASE ontologyv1 IF NOT EXISTS;
```

```powershell
# From repo root
$env:NEO4J_DATABASE='ontologyv1'
$env:KEEP_VISUAL_ARTIFACTS='true'
python -m v1_single_pass.main
python -m v1_single_pass.visualisation.plot_ontology_sphere `
  -o v1_single_pass/data/visualisation/ontology_sphere.html
```

Open `v1_single_pass/data/visualisation/ontology_sphere.html` in a browser.

| Flag / env | Effect |
|------------|--------|
| `--force-refresh` | Re-fetch Wikipedia and re-embed |
| `KEEP_VISUAL_ARTIFACTS=true` | Write plot inputs under `data/visualisation/artifacts/` |
| `LOUVAIN_RESOLUTION` | Louvain granularity for L1 super-concepts (default `1.0`) |

**Verify in Neo4j** (`:use ontologyv1`):

```cypher
MATCH (c:Chunk) WITH count(c) AS chunks
MATCH (n:Concept) WITH chunks, count(n) AS concepts
MATCH ()-[a:ACTIVATES]->() RETURN chunks, concepts, count(a) AS activates;
```

## Read the code

| Order | File | Role |
|-------|------|------|
| 1 | [`main.py`](../../v1_single_pass/main.py) | `run_pipeline()` orchestration |
| 2 | [`ontology/pipeline.py`](../../v1_single_pass/ontology/pipeline.py) | Stages 1–5: embed, OMP, Louvain |
| 3 | [`ontology/neo4j_uploader.py`](../../v1_single_pass/ontology/neo4j_uploader.py) | Drop + bulk CREATE |
| 4 | [`visualisation/plot_ontology_sphere.py`](../../v1_single_pass/visualisation/plot_ontology_sphere.py) | Sphere HTML visualizer |

## Corpus

**8** Wikipedia articles — first topics from the shared 40-item list in [`corpus/wikipedia_topics.py`](../../corpus/wikipedia_topics.py). v1 slices `WIKIPEDIA_TOPICS[:8]` in [`pipeline.py`](../../v1_single_pass/ontology/pipeline.py) for a smaller in-memory POC run; v2 ingests the full list.

## On disk

| Path | Contents |
|------|----------|
| `v1_single_pass/data/cache/embeddings.npy` | Full $`N \times D`$ matrix |
| `v1_single_pass/data/cache/chunks.json` | Chunk metadata |
| `v1_single_pass/data/visualisation/` | Sphere HTML + artifacts |
| `models/` | Shared SentenceTransformer cache |

## Package layout

```
v1_single_pass/               # python -m v1_single_pass.main
  main.py
  ontology/pipeline.py      # mathematical stages 1–5
  ontology/neo4j_uploader.py
  visualisation/plot_ontology_sphere.py
  cypher/                   # bulk CREATE / DROP
  data/cache/ data/visualisation/
```

**Package README:** [`v1_single_pass/README.md`](../../v1_single_pass/README.md)
**Screenshot (committed example):** [`mvp-topological-manifold-graph-sphere.png`](../assets/mvp-topological-manifold-graph-sphere.png) — v1 POC, 8 articles.
**Interactive sphere:** `v1_single_pass/data/visualisation/ontology_sphere.html` after [Run locally](#run-locally)
