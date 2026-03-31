import chromadb
from database.chroma_client import get_text_collection, get_image_collection
from database.chroma_client import get_session_stats

print("=== ChromaDB Inspection ===")
# Try to use the centralized client logic first
try:
    text_coll = get_text_collection()
    image_coll = get_image_collection()
    print("Collections accessed successfully via chroma_client.py")
except Exception as e:
    print(f"Error accessing collections: {e}")
    # Local fallback
    client = chromadb.PersistentClient(path='vectordb')
    text_coll = client.get_or_create_collection("text_collection")
    image_coll = client.get_or_create_collection("image_collection")

ids = text_coll.get()['ids']
img_ids = image_coll.get()['ids']
print(f"Text vectors total: {len(ids)}")
print(f"Image vectors total: {len(img_ids)}")

if ids:
    print("\nSample text metadata session_ids (first 5):")
    sample = text_coll.get(limit=5, include=['metadatas'])['metadatas']
    print([m.get('session_id', 'NO_ID') for m in sample if m])

if img_ids:
    print("\nSample image metadata session_ids (first 5):")
    sample = image_coll.get(limit=5, include=['metadatas'])['metadatas']
    print([m.get('session_id', 'NO_ID') for m in sample if m])

print("\nChat history sample session_ids (if any):")
try:
    import json
    if os.path.exists('data/chat_history.json'):
        with open('data/chat_history.json') as f:
            data = json.load(f)
        print([chat.get('chat_id', chat.get('title', 'Unknown')) for chat in data[:3]])
except Exception as e:
    print(f"No chat_history.json or error: {e}")

print("\nRunning test search with first found session ID...")
if ids:
    sample_m = text_coll.get(limit=1, include=['metadatas'])['metadatas']
    if sample_m and sample_m[0]:
        sid = sample_m[0].get('session_id')
        print(f"Testing session: {sid}")
        from retrieval.search import search
        result = search("test query", sid, top_k_text=1)
        print(f"Text context length: {len(result.get('text_context', ''))}")
        print(f"Images found: {len(result.get('image_paths', []))}")

print("=== END ===")
