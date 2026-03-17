from database.chroma_client import get_text_collection, get_image_collection
from models.embedding_model import embed_clip_text, embed_text
from retrieval.reranker import rerank

def search(query, strategy="text search"):
    text_collection = get_text_collection()
    image_collection = get_image_collection()

    text_context = ""
    image_context = None

    # Always search for text to provide context, but rerank and prioritize based on strategy
    text_results = text_collection.query(
        query_embeddings=[embed_text(query)],
        n_results=10,
        include=["documents"]
    )

    documents = []
    if text_results["documents"] and text_results["documents"][0]:
        documents.extend(text_results["documents"][0])

    if documents:
        # Rerank to find the most relevant text snippets
        top_docs = rerank(query, documents)[:3]
        text_context = "\n".join(top_docs)

    # If the strategy is 'image search', we also perform a targeted image query
    if strategy == "image search":
        try:
            clip_embedding = embed_clip_text(query)
            image_results = image_collection.query(
                query_embeddings=[clip_embedding],
                n_results=1,
                include=["documents"]
            )
            if image_results and image_results["documents"] and image_results["documents"][0]:
                image_context = image_results["documents"][0][0]  # take the first image
        except Exception as e:
            print(f"Image search failed: {e}")
            pass  # Gracefully fail and proceed without image context

    if not text_context and not image_context:
        return {"text_context": "No relevant documents found.", "image_context": None}

    return {"text_context": text_context, "image_context": image_context}
