from retrieval.search import search


def agent_query(user_query):

    print("Agent planning retrieval...")

    # Decide strategy
    if "image" in user_query.lower() or "figure" in user_query.lower():
        strategy = "image search"
    else:
        strategy = "text search"

    print("Agent strategy:", strategy)

    # Execute retrieval
    context = search(user_query, strategy=strategy)

    return context