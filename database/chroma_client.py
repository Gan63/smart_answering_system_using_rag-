import chromadb
from chromadb.utils import embedding_functions
from config import CHROMA_PATH, TEXT_MODEL_NAME

# Centralized Chroma client
client = None

def get_chroma_client():
    global client
    if client is None:
        print("Initializing Chroma client...")
        client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client

def get_text_collection():
    """Gets or creates the global text collection."""
    client = get_chroma_client()
    embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=TEXT_MODEL_NAME)
    collection = client.get_or_create_collection(
        name="text_collection",
        embedding_function=embedding_function,
        metadata={"hnsw:space": "cosine"} # Add this for cosine similarity
    )
    return collection

def get_image_collection():
    """Gets or creates the global image collection."""
    client = get_chroma_client()
    collection = client.get_or_create_collection(
        name="image_collection",
        metadata={"hnsw:space": "cosine"} # Add this for cosine similarity
    )
    return collection

def delete_session_data(session_id: str):
    """Deletes all data associated with a session_id from all collections."""
    if not session_id:
        raise ValueError("session_id must be provided to delete data.")

    text_collection = get_text_collection()
    image_collection = get_image_collection()

    text_collection.delete(where={"session_id": session_id})
    image_collection.delete(where={"session_id": session_id})

    print(f"✅ All data for session {session_id} has been deleted.")
