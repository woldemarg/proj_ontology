UNWIND $concepts AS c
MERGE (n:Concept {id: c.id})
ON CREATE SET
    n.level = 0,
    n.chunk_count = c.chunk_count,
    n.last_updated_batch = c.last_updated_batch,
    n.embedding = c.embedding,
    n.created_at = c.created_at
ON MATCH SET
    n.chunk_count = c.chunk_count,
    n.last_updated_batch = c.last_updated_batch,
    n.embedding = c.embedding,
    n.created_at = coalesce(n.created_at, c.created_at)
