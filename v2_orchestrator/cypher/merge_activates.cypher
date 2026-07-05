UNWIND $activations AS activation
MATCH (chunk:Chunk {id: activation.chunk_id})
MATCH (concept:Concept {id: activation.concept_id})
MERGE (chunk)-[r:ACTIVATES]->(concept)
SET r.weight = activation.weight
