UNWIND $hierarchy_links AS link
MATCH (parent:Concept {id: link.source}),
      (child:Concept {id: link.target})
CREATE (parent)-[:SUPER_CONCEPT_OF]->(child)
