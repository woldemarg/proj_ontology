UNWIND $activations AS activation
MATCH (chunk:Chunk {id: activation.chunk_id}),
      (concept:Concept {id: activation.concept_id})
CREATE (chunk)-[:ACTIVATES {weight: activation.weight}]->(concept)
