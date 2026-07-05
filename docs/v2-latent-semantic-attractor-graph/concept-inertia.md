# v2 — Concept inertia

Concepts in the Latent Semantic Attractor Graph are **living centroids**, not frozen dictionary atoms from a one-shot OMP pass. Each time a chunk activates a concept, that concept's position on the unit hypersphere moves slightly toward the chunk embedding. Early in a concept's life it adapts quickly to find its semantic niche; as more chunks accumulate, updates become smaller so mature attractors resist noise and outlier chunks. This **decaying learning rate** — concept inertia — lets the graph track **semantic drift** across batches (e.g. evolving news topics) without collapsing stable themes or whipsawing under sparse activations.

Formally, the centroid update is an exponential moving average (EMA) with a mass-dependent step size:

```math
c_{\text{new}} = \mathrm{normalize}\bigl((1 - \alpha') c_{\text{old}} + \alpha' x_{\text{chunk}}\bigr)
```

The effective learning rate $`\alpha'`$ is **not constant** — it decays as the concept accumulates supporting chunks:

```math
\alpha' = \max\left(0.01,\; \frac{\alpha}{\sqrt{\text{chunk\_count} + 1}}\right)
```

where $`\alpha`$ is `CENTROID_ALPHA` (default `0.05`). A concept with `chunk_count = 0` uses the full base rate; a concept with thousands of activations barely moves per update (floor `0.01`). Tune `CENTROID_ALPHA` up for fast-drifting corpora, down for stable domains — and watch `centroid_drift` in `metrics.csv`.

**Implementation:** `ConceptStore.update_concept_centroid()` in [`storage.py`](../../v2_orchestrator/storage.py).

**Tuning:** see [configuration.md](configuration.md) · **Pipeline context:** [data-flow.md](data-flow.md)
