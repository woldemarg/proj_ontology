// Lookup — fetch chunks by id (see README § Neo4j Schema & Querying, query 1)
MATCH (chunk:Chunk)
WHERE chunk.id IN [0, 1, 2]
RETURN chunk
ORDER BY chunk.id
