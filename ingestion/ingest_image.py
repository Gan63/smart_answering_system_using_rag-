import os
import time
import uuid
from database.chroma_client import get_image_collection
from models.embedding_model import embed_image

def ingest_image(image_path, session_id: str):
    source_name = os.path.basename(image_path)
    print(f"📸 Processing image: {source_name} (session: {session_id})")
    try:
        embedding = embed_image(image_path)
        print("✅ Embedding created")
    except Exception as e:
        print(f"❌ Image embedding failed for {image_path}: {str(e)}")
        return

    collection = get_image_collection()

    try:
        collection.add(
            ids=[str(uuid.uuid4())],
            embeddings=[embedding],
            documents=[image_path],
            metadatas=[{"source": source_name, "session_id": session_id, "type": "image", "timestamp": str(time.time())}]
        )
        print("✅ Stored in DB")
    except Exception as e:
        print(f"❌ Image add to Chroma failed: {str(e)}")
        return

    print(f"🎉 Image processing complete for session {session_id}")

