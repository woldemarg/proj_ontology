# v1 — Graph shape & Neo4j schema

## Symbolic graph (L0 + L1)

```mermaid
flowchart TB
    subgraph leaves ["Text layer"]
        CH1[Chunk]
        CH2[Chunk]
    end

    subgraph L0 ["Concept L0 - OMP atoms"]
        C1[Concept]
        C2[Concept]
    end

    subgraph L1 ["Concept L1 - Louvain"]
        S1[Super-concept]
    end

    CH1 -->|ACTIVATES| C1
    CH2 -->|ACTIVATES| C2
    C1 ---|RELATED_TO| C2
    S1 -->|SUPER_CONCEPT_OF| C1
    S1 -->|SUPER_CONCEPT_OF| C2
```

## Neo4j schema (v1 only)

| Node | Represents | Key edges |
|------|------------|-----------|
| `Chunk` | Text leaf | `-[:ACTIVATES]->` Concept |
| `Concept` **(L0)** | OMP dictionary atom | `-[:RELATED_TO]-` peers |
| `Concept` **(L1)** | Louvain super-concept | `-[:SUPER_CONCEPT_OF]->` L0 |

L0 concepts carry `density` (activation count). **v2** uses L0-only concepts with `chunk_count` instead of L1 hierarchy.

## RAG traversal

v1 and v2 share `Chunk` → `ACTIVATES` → `Concept` → `RELATED_TO` traversal. Hub filter and multi-seed queries work on both graphs — see [Root README — RAG](../../README.md#rag--graph-traversal) and [`docs/cypher/queries/`](../cypher/queries/README.md).

**Manual index:** [README.md](README.md)
