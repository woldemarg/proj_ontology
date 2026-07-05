// RAG subgraph — multi-hop manifold + coverage-ranked chunks (README query 3)
// Requires Neo4j 5+ (CALL subqueries with imported variables). Tune entry chunk ids.

// 0. Anchor Phase: Translate random chunk IDs into stable Seed Concepts
MATCH (seed_chunk:Chunk)-[:ACTIVATES]->(seed_concept:Concept)
WHERE seed_chunk.id IN [0, 1, 2]
// This WITH DISTINCT command severs the query from the random initial chunks.
// The graph traversal will now originate PURELY from the matched concepts.
WITH DISTINCT seed_concept

// 1. Expand Phase: Traverse the manifold from the Seed Concepts
// *0..3 includes the seed_concept at hop 0 — no array concatenation needed.
MATCH (seed_concept)-[:RELATED_TO*0..3]-(n:Concept)
WITH DISTINCT n

// 2. Filter Phase: Drop massive hubs to keep context focused
// Calculate node degree dynamically — works on v1 and v2 without density/chunk_count
WHERE count { (n)-[:RELATED_TO]-() } <= 10
WITH collect(n) AS filtered_concepts

// 3. RAG Selection: Find the highest coverage chunks for this pure concept neighborhood
CALL (filtered_concepts) {
    UNWIND filtered_concepts AS n
    MATCH (chunk:Chunk)-[:ACTIVATES]->(n)
    WITH chunk, count(DISTINCT n) AS coverage
    ORDER BY coverage DESC, coalesce(size(chunk.text), 0) DESC
    RETURN collect(DISTINCT chunk)[0..10] AS selected_chunks
}

// 4. Graph Topology: Draw the lateral edges among the filtered concepts
CALL (filtered_concepts) {
    UNWIND filtered_concepts AS n
    MATCH (n)-[relation:RELATED_TO]-(peer:Concept)
    WHERE peer IN filtered_concepts
    RETURN DISTINCT n, relation, peer
}

// 5. Final Assembly: Attach the selected RAG chunks to the concept graph
WITH n, relation, peer, selected_chunks
UNWIND selected_chunks AS chunk
MATCH (chunk)-[activation:ACTIVATES]->(n)

// Return the clean, concept-anchored subgraph
RETURN DISTINCT n, relation, peer, chunk, activation
LIMIT 500
