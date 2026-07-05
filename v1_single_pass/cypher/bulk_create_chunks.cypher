UNWIND $chunks AS chunk
CREATE (:Chunk {
    id: chunk.id,
    text: chunk.text,
    source: chunk.source,
    article: chunk.article,
    article_label: chunk.article_label
})
