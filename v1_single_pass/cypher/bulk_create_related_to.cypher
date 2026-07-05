UNWIND $relations AS relation
MATCH (source:Concept {id: relation.source}),
      (target:Concept {id: relation.target})
CREATE (source)-[:RELATED_TO {weight: relation.weight}]->(target)
