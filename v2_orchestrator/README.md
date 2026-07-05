# v2_orchestrator — Latent Semantic Attractor Graph

Runnable package for **v2**: streaming batches, living centroids, disk journal, MERGE Neo4j upserts. **Corpus:** all **40** topics from [`corpus/wikipedia_topics.py`](../corpus/wikipedia_topics.py).

| | |
|---|---|
| **Manual** | [`docs/v2-latent-semantic-attractor-graph/`](../docs/v2-latent-semantic-attractor-graph/README.md) |
| **Run locally** | [operations.md](../docs/v2-latent-semantic-attractor-graph/operations.md#run-locally) |
| **Data flow** | [data-flow.md](../docs/v2-latent-semantic-attractor-graph/data-flow.md) |
| **Tuning** | [configuration.md](../docs/v2-latent-semantic-attractor-graph/configuration.md) |

```powershell
$env:NEO4J_DATABASE='ontologyv2'
python -m v2_orchestrator.main --reset --max-batches 8 --articles-per-batch 5 --plot
```

**Modules:** `python -m v2_orchestrator.main` → `storage.py` → `ontology_engine.py` → `neo4j_uploader.py` → `chunk_journal.py` — see [operations.md](../docs/v2-latent-semantic-attractor-graph/operations.md#read-the-code).
