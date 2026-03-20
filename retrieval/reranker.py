# Lazy loading
reranker = None

def get_reranker():
    global reranker
    if reranker is None:
        from sentence_transformers import CrossEncoder
        reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return reranker

def rerank(query, documents):
    if not documents:
        return []

    model = get_reranker()
    pairs = [[query, doc] for doc in documents]

    scores = model.predict(pairs)

    scored_docs = list(zip(documents, scores))

    scored_docs.sort(key=lambda x: x[1], reverse=True)

    top_docs = [doc for doc, score in scored_docs[:3]]

    return top_docs

