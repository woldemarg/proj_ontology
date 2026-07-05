# v2 — Environment variables

Set in repo-root **`.env`** ([`.env.sample`](../../.env.sample)). Use Neo4j database **`ontologyv2`**.

CLI flags and run workflow: [operations.md](operations.md) · full variable list: [`.env.sample`](../../.env.sample).

---

## Start here — three knobs that shape your graph

| Variable | Default | What it does | How to tune |
|----------|---------|--------------|-------------|
| **`MIN_ASSIGN_THRESHOLD`** | `0.30` | Floor for chunk→concept cosine. Below → **orphan** (buffered for OMP). | Noisy corpus: `0.25`–`0.28`. Narrow domain: `0.32`–`0.35`. |
| **`ADAPTIVE_PERCENTILE`** | `85` | When ≥10 concepts exist, threshold = percentile of concept–concept cosines, clamped to `[MIN, MAX]`. | Stricter graph: `88`–`92`. Looser RAG recall: `75`–`80`. |
| **`RELATED_TO_PEER_COUNT`** | `7` | Top-k neighbors per concept **before** mutual k-NN filter. | Denser RAG: `9`–`11`. Sparser: `5`–`6`. Expect ~4–5 avg degree with default `7`. |

### Corpus profiles

| Profile | Starting suggestion |
|---------|---------------------|
| Fast-moving (news) | `CENTROID_ALPHA=0.07`, `ADAPTIVE_PERCENTILE=82`, watch `centroid_drift` |
| Stable technical (docs, specs) | `CENTROID_ALPHA=0.03`, `ADAPTIVE_PERCENTILE=88`, `MIN_ASSIGN_THRESHOLD=0.32` |
| Broad exploratory (Wikipedia-like) | Defaults; tune after 4–8 batches using `metrics.csv` |

---

## All variables (reference)

### Assignment & orphans

| Variable | Default | Notes |
|----------|---------|-------|
| `MAX_ASSIGN_THRESHOLD` | `0.45` | Hard ceiling on adaptive threshold |
| `TOP_K_ASSIGN` | `2` | Max concepts per chunk when above threshold |
| `MIXTURE_RATIO` | `0.90` | Secondary winner must score ≥ `best × ratio` |
| `CENTROID_ALPHA` | `0.05` | Base EMA rate — see [concept-inertia.md](concept-inertia.md) |
| `SOFT_MERGE_LOW` | `0.55` | Absorb OMP atom into existing centroid if cosine above |
| `ORPHAN_BUFFER_MIN_FACTOR` | `3` | Full OMP when buffer ≥ `DICTIONARY_K_MIN × factor` |

### Graph topology

| Variable | Default | Notes |
|----------|---------|-------|
| `RELATED_TO_MIN_WEIGHT` | `0.15` | Minimum cosine for `RELATED_TO` edge |

### OMP & ingest (shared with v1)

| Variable | Default | Notes |
|----------|---------|-------|
| `ARTICLES_PER_BATCH` | `2` | Overridden by `--articles-per-batch` |
| `CONCEPTS_PER_CHUNK` | `2` | OMP sparsity cap |
| `DICTIONARY_K_MIN` / `K_STEP` | `20` / `20` | OMP dictionary sweep |
| `MAX_CONCEPT_COUNT` | `200` | Cap on dictionary K |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `1024` / `128` | Text segmentation |

---

## Tuning workflow

1. Run 4–8 batches with defaults ([operations.md](operations.md)).
2. Open `v2_orchestrator/data/state/metrics.csv`.
3. `orphan_rate` > 0.4 after batch 3 → lower `MIN_ASSIGN_THRESHOLD` or `ADAPTIVE_PERCENTILE`.
4. `avg_degree` < 3 → raise `RELATED_TO_PEER_COUNT`.
5. `centroid_drift` spikes → lower `CENTROID_ALPHA`.

**CLI:** `--reset` · `--max-batches N` · `--articles-per-batch N` · `--plot` · `--draw-edges` / `--no-draw-edges` · `--no-verify`

`--plot` writes artifacts and invokes the shared sphere plotter (`python -m v1_single_pass.visualisation.plot_ontology_sphere`) against `v2_orchestrator/data/visualisation/artifacts/`.
