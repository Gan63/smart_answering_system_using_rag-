import chromadb
from database.chroma_client import get_text_collection, get_image_collection
from database.chroma_client import get_session_stats

print("=== ChromaDB Inspection ===")
client = chromadb.PersistentClient(path='vectordb')
collections = client.list_collections()
print(f\"Collections: {[c.name for c in collections]}\")

text_coll = get_text_collection()
image_coll = get_image_collection()
print(f\"Text vectors: {len(text_coll.get()['ids'])}\")
print(f\"Image vectors: {len(image_coll.get()['ids'])}\")

print(\"\\nSample text metadata session_ids:\")
sample = text_coll.get(limit=5)['metadatas']
print([m.get('session_id', 'NO_ID') for m in sample])

print(\"\\nSample image metadata session_ids:\")
sample = image_coll.get(limit=5)['metadatas']
print([m.get('session_id', 'NO_ID') for m in sample])

print(\"\\nChat history sample session_ids (if any):\")
try:
    import json
    with open('data/chat_history.json') as f:
        data = json.load(f)
    print([chat.get('chat_id', chat['title']) for chat in data[:3]])
except:
    print(\"No chat_history.json or error\")

print(\"\\nTest search with sample session '68ca78a4-6d8f-45f9-b3db-d54c765452ee':\")
from retrieval.search import search
result = search(\"test query\", \"68ca78a4-6d8f-45f9-b3db-d54c765452ee\", top_k_text=1)
print(f\"Text context len: {len(result.get('text_context', ''))}, Images: {len(result.get('image_paths', []))}\")
print(\"=== END ===\")

