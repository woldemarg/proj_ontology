UNWIND $chunks AS chunk
MERGE (c:Chunk {id: chunk.id})
SET c.text = chunk.text,
    c.source = chunk.source,
    c.article = chunk.article,
    c.article_label = chunk.article_label
