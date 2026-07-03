# proj_ontology: Autonomous Latent Knowledge Graph

This Proof-of-Concept (POC) builds a machine-readable knowledge graph directly from the geometry of text embeddings. Instead of relying on human labeling or LLM extraction, it uses **sparse dictionary learning (OMP)** to discover latent semantic concepts, wires them into a traversable graph, and publishes the architecture to **Neo4j** for advanced Retrieval-Augmented Generation (RAG).

Entry point: `script/main.py` · Pipeline: `script/ontology/` · Cypher: `script/cypher/`

---

## 🚀 Quick Start

**1. Prerequisites**

- Python 3.10+
- A running Neo4j instance (Bolt enabled)

**2. Install & Configure**

```bash
pip install -r requirements.txt
cp .env.sample .env
```

Edit `.env` with your Neo4j credentials (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`). Tuning knobs (`CONCEPTS_PER_CHUNK`, `RELATED_TO_PEER_COUNT`, chunk size, K-sweep bounds) are documented in `.env.sample`.

**3. Run the Pipeline**

```bash
python script/main.py
```

Optional: bypass caches without deleting `data/cache/`:

```bash
python script/main.py --force-refresh
```

The script caches articles, chunks, and embeddings in `data/cache/`. Delete that directory (or use `--force-refresh`) to force a full rebuild. The SentenceTransformer model is cached under `models/sentence-transformers/` (not committed — downloaded on first run).

Interactive use (Spyder / VS Code): open `script/main.py`, run the `#%%` cells, then call `run_pipeline()`.

---



## 🧠 Under the Hood (How it Works)

The pipeline transforms unstructured Wikipedia articles into a structured, 3-tier graph in four distinct phases:

### Phase 1: Ingestion & Vector Preparation

- **Chunking:** Downloads 8 Wikipedia topics (`WIKIPEDIA_TOPICS` in `pipeline.py`) and splits them into 1,024-character chunks with 128-character overlap (defaults: `CHUNK_SIZE`, `CHUNK_OVERLAP`).
- **Embedding:** Converts chunks into 384-dimensional vectors via `paraphrase-multilingual-MiniLM-L12-v2`.
- **Anisotropy correction:** Subtracts the mean vector and L2-normalizes each embedding onto the unit sphere so semantic directions spread evenly instead of collapsing into a cone.



### Phase 2: Concept Discovery (Sparse Coding)

- **Orthogonal Matching Pursuit (OMP):** Instead of spatial clustering (e.g. K-Means), every chunk is treated as a sparse mixture of latent topics. `MiniBatchDictionaryLearning` with `transform_algorithm="omp"` discovers pure dictionary atoms (Concepts).
- **Strict sparsity:** OMP assigns exactly `CONCEPTS_PER_CHUNK` non-zero activations per chunk (default **2**).
- **Adaptive sizing:** Sweeps concept count **K** from 20 to 200 in steps of 20, stopping on reconstruction-error plateau and dead-concept penalties. Orphan concepts with zero chunk usage are pruned before graph wiring.



### Phase 3: Graph Topology

- **Leaves (**`ACTIVATES`**):** Each chunk links to its top winning concepts with weighted `ACTIVATES` edges — chunks are leaf nodes.
- **Semantic web (**`RELATED_TO`**):** Cosine similarity across concept embeddings; each concept connects to its top `RELATED_TO_PEER_COUNT` peers (default **5**) when similarity exceeds `RELATED_TO_MIN_WEIGHT` (default **0.15**). Pairs are deduplicated so edges are undirected and unique.
- **Emergent taxonomy (**`SUPER_CONCEPT_OF`**):** Louvain community detection on the `RELATED_TO` graph groups dense neighborhoods into level-1 Super Concepts pointing down to level-0 children.



### Phase 4: Database Publishing

- Drops existing nodes in batched deletes (`NEO4J_DELETE_BATCH_SIZE`).
- Creates uniqueness constraints on `Chunk.id` and `Concept.id`.
- Bulk-loads nodes and relationships via external `UNWIND` Cypher files, sliced by `NEO4J_LOAD_BATCH_SIZE` (default 5,000).

---



## 🗺️ Neo4j Schema & Querying


| Node Type          | Represents                | Key Edges                            |
| ------------------ | ------------------------- | ------------------------------------ |
| `Chunk`            | Raw ground-truth text     | `-[:ACTIVATES]->` Concept            |
| `Concept` **(L0)** | Dictionary atoms from OMP | `-[:RELATED_TO]-` peer pathways      |
| `Concept` **(L1)** | Louvain super-concepts    | `-[:SUPER_CONCEPT_OF]->` L0 children |


All examples below use the same entry chunk ids: **105, 65, 300**. The same queries are saved under `script/cypher/queries/` for use in Neo4j Browser.

### 1. Lookup — fetch chunks by id

```cypher
MATCH (chunk:Chunk)
WHERE chunk.id IN [105, 65, 300]
RETURN chunk
ORDER BY chunk.id
```



### 2. Local traversal — chunk → concept → peers

```cypher
MATCH (chunk:Chunk)-[ac:ACTIVATES]->(concept:Concept)
WHERE chunk.id IN [105, 65, 300]
MATCH (concept)-[rel:RELATED_TO*1..2]-(peer:Concept)
RETURN chunk, ac, concept, rel, peer
LIMIT 500
```



### 3. RAG subgraph — multi-hop manifold + coverage-ranked chunks

Builds a focused concept neighborhood, filters hub concepts by `density`, selects up to 10 chunks with the broadest concept coverage, and returns the exact graph slice for context injection.

```cypher
// 0. Entry point: start from specific chunks by id
MATCH (start_chunk:Chunk)-[:ACTIVATES]->(start_concept:Concept)
WHERE start_chunk.id IN [105, 65, 300]

// 1. Expand: traverse the semantic manifold via RELATED_TO
MATCH (start_concept)-[:RELATED_TO*1..5]-(concept:Concept)
WITH collect(DISTINCT concept) + collect(DISTINCT start_concept) AS concepts
UNWIND concepts AS n
WITH DISTINCT n

// 2. Filter concepts: ignore massive hubs to keep context focused
// Uses the 'density' property calculated during ontology extraction
WHERE n.density <= 10
WITH collect(n) AS filtered_concepts

// 3. Select RAG chunks: prefer chunks that cover the most concepts in this neighborhood
CALL {
    WITH filtered_concepts
    UNWIND filtered_concepts AS n
    MATCH (chunk:Chunk)-[:ACTIVATES]->(n)
    WITH chunk, count(DISTINCT n) AS coverage
    ORDER BY coverage DESC, size(chunk.text) DESC
    RETURN collect(DISTINCT chunk)[0..10] AS selected_chunks
}

// 4. Build concept graph: lateral RELATED_TO edges among filtered concepts
CALL {
    WITH filtered_concepts
    MATCH (n)-[relation:RELATED_TO]-(peer:Concept)
    WHERE peer IN filtered_concepts
    RETURN DISTINCT n, relation, peer
}

// 5. Attach only the selected RAG chunks to the concept graph
WITH n, relation, peer, selected_chunks
UNWIND selected_chunks AS chunk
MATCH (chunk)-[activation:ACTIVATES]->(n)

// Final subgraph for RAG context
RETURN DISTINCT n, relation, peer, chunk, activation
LIMIT 500
```

---



## 🚧 POC Limitations & Scaling Roadmap

This architecture is stable and performant for roughly **10,000 chunks** and a few hundred concepts. Beyond that, the OMP manifold and in-Python graph steps hit structural ceilings. Production scale (~50,000+ chunks) needs the shifts below.


| Component               | Current POC limitation                                                                           | Production direction                                                                                                         |
| ----------------------- | ------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| **Peer discovery**      | Dense `cosine_similarity` on concept vectors — O(K^2) today; O(N^2) if moved to chunk-level k-NN | **ANN** libraries (FAISS, hnswlib, Annoy) for O(N \log N) top-k search                                                       |
| **Community detection** | NetworkX Louvain in Python memory (degrades past ~5,000+ dense nodes)                            | **Neo4j Graph Data Science (GDS)** — Leiden/Louvain on the stored graph                                                      |
| **Data ingestion**      | Full drop and rebuild on every `run_pipeline()` call                                             | **Streaming ingestion** — map new chunks to existing concepts or spawn nodes incrementally                                   |
| **Concept extraction**  | OMP K-sweep over the full embedding matrix scales poorly                                         | **Pure geometry** — mutual k-NN on chunk embeddings → Leiden/Louvain centroids                                             |


---



## Repository layout

```
proj_ontology/
  .env.sample          # copy to .env — all tunables documented
  .gitignore
  requirements.txt
  README.md
  data/
    cache/             # runtime cache (gitignored except .gitkeep)
  models/              # embedding model cache (gitignored except .gitkeep)
  script/
    main.py            # entry point
    cypher/
      *.cypher         # pipeline load queries (used by neo4j_uploader)
      queries/         # sample RAG exploration queries (README-aligned)
    ontology/
      settings.py      # .env loader
      pipeline.py      # ingest, embed, build_ontology_graph
      neo4j_uploader.py
```



### What is not in git


| Path                             | Reason                                             |
| -------------------------------- | -------------------------------------------------- |
| `.env`                           | Secrets — copy from `.env.sample`                  |
| `data/cache/*`                   | Regenerated from Wikipedia on first run (~minutes) |
| `models/sentence-transformers/*` | Downloaded by SentenceTransformer on first run     |




### First run expectations

1. `pip install -r requirements.txt` — pulls PyTorch via `sentence-transformers`.
2. `python script/main.py` — fetches 8 Wikipedia articles, embeds ~1k chunks, runs OMP sweep, publishes to Neo4j.
3. Open Neo4j Browser and run queries from `script/cypher/queries/`.