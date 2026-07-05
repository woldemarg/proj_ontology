UNWIND $concepts AS concept
CREATE (:Concept {
    id: concept.id,
    name: concept.name,
    level: concept.level,
    density: concept.density
})
