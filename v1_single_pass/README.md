# v1_single_pass — Topological Manifold

Runnable package for **v1**: one-shot ingest, OMP K-sweep, Louvain L1, prosphera sphere, Neo4j bulk publish. **Corpus:** first **8** topics from [`corpus/wikipedia_topics.py`](../corpus/wikipedia_topics.py).

| | |
|---|---|
| **Manual** | [`docs/v1-topological-manifold/`](../docs/v1-topological-manifold/README.md) |
| **Run locally** | [operations.md](../docs/v1-topological-manifold/operations.md#run-locally) |
| **Math & schema** | [mathematical-foundations.md](../docs/v1-topological-manifold/mathematical-foundations.md) · [graph-schema.md](../docs/v1-topological-manifold/graph-schema.md) |

```powershell
$env:NEO4J_DATABASE='ontologyv1'
python -m v1_single_pass.main
```

**Modules:** `python -m v1_single_pass.main` → `ontology/pipeline.py` → `ontology/neo4j_uploader.py` → `python -m v1_single_pass.visualisation.plot_ontology_sphere` — see [operations.md](../docs/v1-topological-manifold/operations.md#read-the-code).
