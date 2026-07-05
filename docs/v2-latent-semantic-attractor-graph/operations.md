# v2 — Operations & codebase

## Run locally

**Prerequisites:** Python 3.10+, Neo4j (Bolt), repo-root [`.env`](../../.env.sample).

```cypher
CREATE DATABASE ontologyv2 IF NOT EXISTS;
```

```powershell
# From repo root
$env:NEO4J_DATABASE='ontologyv2'
$env:KEEP_VISUAL_ARTIFACTS='true'
python -m v2_orchestrator.main --reset --max-batches 8 --articles-per-batch 5 --plot

python -m v2_orchestrator.tests.verify_smoke
python -m v2_orchestrator.tests.verify_neo4j
```

| Goal | Command |
|------|---------|
| Resume | `python -m v2_orchestrator.main` |
| Wipe state + Neo4j | `--reset` (clears `data/state/`, `data/cache/`, viz; drops Neo4j DB contents) |
| Backfill Neo4j from disk | `python -m v2_orchestrator.tests.verify_neo4j --sync` |
| Offline batch smoke test | `python -m v2_orchestrator.tests.verify_smoke` (mock Neo4j) |

**Screenshot (committed example):** [`mvp-latent-semantic-attractor-graph-sphere.png`](../assets/mvp-latent-semantic-attractor-graph-sphere.png) — v2 MVP, 40 articles. Live copy: `v2_orchestrator/data/visualisation/ontology_sphere.html` (with `--plot` or `KEEP_VISUAL_ARTIFACTS=true`).

## Corpus

**40** Wikipedia articles — full list in [`corpus/wikipedia_topics.py`](../../corpus/wikipedia_topics.py) (imported by [`ingest.py`](../../v2_orchestrator/ingest.py)). Default quick start (`--max-batches 8 --articles-per-batch 5`) processes all 40 topics in one run.

## Read the code

| Order | File | Role |
|-------|------|------|
| 1 | [`main.py`](../../v2_orchestrator/main.py) | `run_batch()` — lifecycle orchestration |
| 2 | [`storage.py`](../../v2_orchestrator/storage.py) | `ConceptStore`, inertia, `global_mean` |
| 3 | [`ontology_engine.py`](../../v2_orchestrator/ontology_engine.py) | Assign, OMP extract, mutual k-NN |
| 4 | [`neo4j_uploader.py`](../../v2_orchestrator/neo4j_uploader.py) | MERGE upserts |
| 5 | [`chunk_journal.py`](../../v2_orchestrator/chunk_journal.py) | Disk journal |
| 6 | [`observability.py`](../../v2_orchestrator/observability.py) | `metrics.csv`, invariants |

## On disk

| Path | Contents |
|------|----------|
| `v2_orchestrator/data/state/state.json` | Offsets, IDs, `processed_topic_offset` |
| `v2_orchestrator/data/state/concepts.npz` | Centroids, `global_mean`, `chunk_counts`, `concept_ids` |
| `v2_orchestrator/data/state/orphan_buffer.npz` | Pending orphan embeddings (when non-empty) |
| `v2_orchestrator/data/state/metrics.csv` | Per-batch health |
| `v2_orchestrator/data/cache/chunks.jsonl` | Append-only chunk journal |
| `v2_orchestrator/data/cache/activations.jsonl` | Append-only `ACTIVATES` journal |
| `v2_orchestrator/data/cache/embeddings.mmap` | Centered chunk embedding memmap |
| `v2_orchestrator/data/visualisation/` | Sphere HTML + artifacts (`KEEP_VISUAL_ARTIFACTS` or `--plot`) |

## `metrics.csv` signals

| Column | Healthy signal |
|--------|----------------|
| `orphan_rate` | Falls as attractors accumulate |
| `new_extracted` / `new_kept` | Tapers after early batches |
| `soft_merged` | Often 0 — not a failure |
| `avg_degree` | ~4–5 with default `RELATED_TO_PEER_COUNT` |
| `max_concept_density_pct` | Watch for hub >25% (warning in logs) |
| `centroid_drift` | Stable band after warmup |
| `adaptive_thresh` | Tracks `ADAPTIVE_PERCENTILE` band |

## Module layout

```
v2_orchestrator/              # python -m v2_orchestrator.main
  main.py                     # batch loop
  storage.py                  # ConceptStore + inertia
  ontology_engine.py          # assign / OMP / mutual k-NN topology
  neo4j_uploader.py           # MERGE publisher
  chunk_journal.py            # chunks.jsonl / activations.jsonl / embeddings.mmap
  observability.py            # metrics.csv + invariants
  ingest.py                   # live Wikipedia per batch
  viz_export.py               # sphere artifacts + --plot bridge
  reset.py                    # --reset workspace wipe
  verification.py             # E2E invariants
  cypher/                     # MERGE queries (pipeline load)
  data/state/ data/cache/ data/visualisation/
  tests/verify_smoke.py       # offline mock-Neo4j smoke
  tests/verify_neo4j.py       # live Neo4j E2E + --sync
```

**Package README:** [`v2_orchestrator/README.md`](../../v2_orchestrator/README.md)
