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

    # Increase initial retrieval to 50 so reranker has a pool to work with
    retrieval_limit = max(50, top_k_text)
    
    print(f"DEBUG SEARCH text query (retrieval_limit={retrieval_limit})...")
    text_results = text_collection.query(
        query_embeddings=[embed_text(query)],
        n_results=retrieval_limit,
        where={"session_id": session_id},
        include=["documents", "metadatas"]
    )
    print(f"DEBUG SEARCH text results_count={len(text_results.get('documents', [[ ]])[0]) if 'documents' in text_results else 0}")

    # Fixed duplicate code
    raw_docs = text_results["documents"][0] if text_results["documents"] and text_results["documents"][0] else []
    raw_metas = text_results["metadatas"][0] if text_results["metadatas"] and text_results["metadatas"][0] else []
    
    print(f"DEBUG documents_len={len(raw_docs)}")

    if raw_docs:
        # Rerank to find the most relevant text snippets
        top_docs = rerank(query, raw_docs)[:top_k_text]
        text_context = "\n".join(top_docs)
        
        # Build text_results list for app.py (sources)
        text_sources = []
        for doc, meta in zip(raw_docs, raw_metas):
            if doc in top_docs:
                text_sources.append({
                    "content": doc,
                    "document": meta.get("source", "Unknown"),
                    "session_id": meta.get("session_id")
                })
    else:
        text_sources = []

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
                include=["documents", "metadatas"]
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
        return {"text_context": "", "image_context": None, "image_paths": [], "text_results": []}

    return {
        "text_context": text_context, 
        "image_context": image_context, 
        "image_paths": image_paths,
        "text_results": text_sources
    }
