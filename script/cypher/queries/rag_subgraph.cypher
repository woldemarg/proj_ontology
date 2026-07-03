// RAG subgraph — multi-hop manifold + coverage-ranked chunks (README query 3)
// Requires Neo4j 5+ (CALL subqueries). Tune entry ids and n.density threshold as needed.

// 0. Entry point: start from specific chunks by id
MATCH (start_chunk:Chunk)-[:ACTIVATES]->(start_concept:Concept)
WHERE start_chunk.id IN [105, 65, 300]

// 1. Expand: traverse the semantic manifold via RELATED_TO
MATCH (start_concept)-[:RELATED_TO*1..5]-(concept:Concept)
WITH collect(DISTINCT concept) + collect(DISTINCT start_concept) AS concepts
UNWIND concepts AS n
WITH DISTINCT n

// 2. Filter concepts: ignore massive hubs to keep context focused
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

RETURN DISTINCT n, relation, peer, chunk, activation
LIMIT 500
