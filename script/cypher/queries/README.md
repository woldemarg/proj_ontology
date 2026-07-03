# Sample Cypher queries for exploring the published ontology graph.
# Run in Neo4j Browser or cypher-shell after `python script/main.py`.
#
# | File | Purpose |
# | --- | --- |
# | lookup_chunks_by_id.cypher | Direct chunk lookup |
# | local_traversal.cypher | Chunk → concept → peers (1–2 hops) |
# | rag_subgraph.cypher | Production-style RAG context subgraph |
