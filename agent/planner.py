from retrieval.search import search

def agent_query(user_query: str, session_id: str):
    """
    Determines the search strategy and calls the search function,
    ensuring the session_id is passed for filtering.
    """
    print(f"DEBUG AGENT - session: {session_id}, query: {user_query[:50]}")
    # Decide strategy based on query keywords
    if any(k in user_query.lower() for k in ["image", "figure", "diagram", "picture", "chart", "graph"]):
        strategy = "image search"
    else:
        strategy = "text search"

    print(f"DEBUG AGENT strategy: {strategy}")
    try:
        context = search(query=user_query, session_id=session_id, strategy=strategy)
        print(f"DEBUG AGENT context keys: {list(context.keys())}")
        return context
    except Exception as e:
        print(f"DEBUG AGENT search error: {e}")
        return {"text_context": "", "image_context": None, "image_paths": []}
