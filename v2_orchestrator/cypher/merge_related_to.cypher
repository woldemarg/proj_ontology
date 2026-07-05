UNWIND $relations AS rel
MATCH (s:Concept {id: rel.source})
MATCH (t:Concept {id: rel.target})
MERGE (s)-[r:RELATED_TO]->(t)
ON CREATE SET
    r.weight = rel.weight,
    r.created_batch = $batch_id
ON MATCH SET
    r.weight = rel.weight,
    r.updated_batch = $batch_id
