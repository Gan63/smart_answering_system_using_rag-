from database.chroma_client import get_text_collection, get_image_collection
from models.embedding_model import embed_clip_text, embed_text
from retrieval.reranker import rerank

def search(query: str, session_id: str, strategy: str = "text search", top_k_text: int = 10, top_k_image: int = 1):
    print(f"SEARCH CALLED strategy={strategy} session={session_id} query='{query[:50]}...'")
    """
    Searches for a query in the database, filtered by session_id.
    Configurable top_k for improved accuracy.
    """
    if not session_id:
        raise ValueError("session_id is required for search.")

    text_collection = get_text_collection()
    image_collection = get_image_collection()

    text_context = ""
    image_context = None
    image_paths = []

    # Always search for text to provide context
    print(f"DEBUG SEARCH text query...")
    text_results = text_collection.query(
        query_embeddings=[embed_text(query)],
        n_results=top_k_text,
        where={"session_id": session_id},
        include=["documents"]
    )
    print(f"DEBUG SEARCH text results_count={len(text_results.get('documents', [[ ]])[0]) if 'documents' in text_results else 0}")

    # Fixed duplicate code
    documents = text_results["documents"][0] if text_results["documents"] and text_results["documents"][0] else []
    print(f"DEBUG documents_len={len(documents)}")

    if documents:
        # Rerank to find the most relevant text snippets
        top_docs = rerank(query, documents)[:10]
        text_context = "\n".join(top_docs)

    # Image search (always for multimodal) - FIXED NoneType
    try:
        clip_embedding = embed_clip_text(query)
        if clip_embedding is None or not isinstance(clip_embedding, list) or len(clip_embedding) == 0:
            print("⚠️ CLIP embedding failed/empty - skipping image search")
            image_paths = []
            image_context = None
        else:
            print(f"✅ CLIP embedding OK, dim={len(clip_embedding)}")
            image_results = image_collection.query(
                query_embeddings=[clip_embedding],
                n_results=top_k_image,
                where={"session_id": session_id},
                include=["documents"]
            )
            image_paths = []
            if image_results and image_results["documents"] and image_results["documents"][0]:
                image_paths = image_results["documents"][0]
                print(f"🖼️ Images retrieved: {len(image_paths)}")
            image_context = image_paths[0] if image_paths else None
    except Exception as e:
        print(f"❌ Image search failed: {e}")
        image_paths = []
        image_context = None

    if not text_context and not image_context:
        return {"text_context": "No relevant documents found for this session.", "image_context": None, "image_paths": []}

    return {"text_context": text_context, "image_context": image_context, "image_paths": image_paths}
