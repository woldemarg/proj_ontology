# Sample Cypher queries for exploring the published ontology graph.
# Run in Neo4j Browser or cypher-shell after `python script/main.py`.
#
# | File | Purpose |
# | --- | --- |
# | lookup_chunks_by_id.cypher | Direct chunk lookup |
# | local_traversal.cypher | Chunk → concept → peers (1–2 hops) |
# | rag_subgraph.cypher | Concept-anchored RAG subgraph (3-hop expand, coverage-ranked chunks; Neo4j 5+) |
