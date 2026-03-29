import chromadb
from database.chroma_client import get_text_collection, get_image_collection
from config import CHROMA_PATH

def inspect_vectors(session_id=None):
    print(f"Chroma path: {CHROMA_PATH}")
    print("\n=== TEXT COLLECTION ===")
    text_coll = get_text_collection()
    print(f"Total count: {text_coll.count()}")
    
    if session_id:
        text_results = text_coll.get(where={"session_id": session_id}, limit=3, include=["embeddings", "documents", "metadatas"])
        print(f"Sample for session {session_id}:")
        for i, (doc, meta, emb) in enumerate(zip(text_results.get('documents', []), text_results.get('metadatas', []), text_results.get('embeddings', []))):
            print(f"  Doc {i}: {doc[:100]}...")
            print(f"  Meta: {meta}")
            print(f"  Embedding shape: {len(emb) if emb else 0}")
            print()
    else:
        # Show overall sample
        sample = text_coll.get(limit=3, include=["embeddings", "documents", "metadatas"])
        for i in range(len(sample.get('ids', []))):
            print(f"  Sample doc {i}: {sample['documents'][i][:100]}...")
    
    print("\n=== IMAGE COLLECTION ===")
    image_coll = get_image_collection()
    print(f"Total count: {image_coll.count()}")
    
    if session_id:
        image_results = image_coll.get(where={"session_id": session_id}, limit=3, include=["embeddings", "documents", "metadatas"])
        print(f"Sample for session {session_id}:")
        for i, (doc, meta, emb) in enumerate(zip(image_results.get('documents', []), image_results.get('metadatas', []), image_results.get('embeddings', []))):
            print(f"  Image {i}: {doc}")
            print(f"  Meta: {meta}")
            print(f"  Embedding shape: {len(emb) if emb else 0}")
            print()
    else:
        sample = image_coll.get(limit=3, include=["embeddings", "documents", "metadatas"])
        for i in range(len(sample.get('ids', []))):
            print(f"  Sample image {i}: {sample['documents'][i]}")

if __name__ == "__main__":
    # List recent sessions or use a known one
    print("Inspect all vectors (first 3 samples each collection):")
    inspect_vectors()
    
    # Example for specific session (replace with your session_id)
    # inspect_vectors("your-session-id-here")

