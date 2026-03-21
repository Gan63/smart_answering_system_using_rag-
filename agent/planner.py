from retrieval.search import search

def agent_query(user_query: str, session_id: str, top_k_text: int = 10, top_k_image: int = 1):
    '''
    Determines the search strategy and calls the search function,
    ensuring the session_id is passed for filtering.
    '''
    print(f"DEBUG AGENT - session: {session_id}, query: {user_query[:50]}")
    # Always use multimodal (images always retrieved in search.py)
    strategy = "multimodal"
    print(f"DEBUG AGENT strategy: {strategy}")
    try:
        context = search(query=user_query, session_id=session_id, strategy=strategy, top_k_text=top_k_text, top_k_image=top_k_image)
        print(f"DEBUG AGENT context keys: {list(context.keys())}")
        return context
    except Exception as e:
        print(f"DEBUG AGENT search error: {e}")
        return {"text_context": "", "image_context": None, "image_paths": []}
