import chromadb
from chromadb.config import Settings
from config import CHROMA_PATH, TEXT_MODEL_NAME

# Centralized Chroma client
client = None

def get_chroma_client():
    global client
    if client is None:
        print("Initializing Chroma client...")
        try:
            client = chromadb.PersistentClient(path=CHROMA_PATH)
        except Exception as e:
            print(f"PersistentClient failed: {e}. Using in-memory client.")
            client = chromadb.Client(Settings(
                anonymized_telemetry=False
            ))
    return client

def get_text_collection():
    """Gets or creates the global text collection."""
    client = get_chroma_client()
    collection = client.get_or_create_collection(
        name="text_collection",
        metadata={"hnsw:space": "cosine"}
    )
    return collection

def get_image_collection():
    """Gets or creates the global image collection."""
    client = get_chroma_client()
    collection = client.get_or_create_collection(
        name="image_collection",
        metadata={"hnsw:space": "cosine"}
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

def get_session_stats(session_id: str) -> dict:
    """Get count of text and image documents for session."""
    text_collection = get_text_collection()
    image_collection = get_image_collection()
    
    try:
        text_results = text_collection.get(where={"session_id": session_id}, include=["metadatas"])
        image_results = image_collection.get(where={"session_id": session_id}, include=["metadatas"])
        return {
            "text_count": len(text_results['ids']) if text_results['ids'] else 0,
            "image_count": len(image_results['ids']) if image_results['ids'] else 0
        }
    except:
        return {"text_count": 0, "image_count": 0}
