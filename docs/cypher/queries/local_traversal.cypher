// Local traversal — chunk → concept → peers (README query 2)
MATCH (chunk:Chunk)-[ac:ACTIVATES]->(concept:Concept)
WHERE chunk.id IN [0, 1, 2]
MATCH (concept)-[rel:RELATED_TO*1..2]-(peer:Concept)
RETURN chunk, ac, concept, rel, peer
LIMIT 500
