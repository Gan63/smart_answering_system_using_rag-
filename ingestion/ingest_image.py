import os
import time
import uuid
from PIL import Image
from database.chroma_client import get_image_collection
from models.embedding_model import embed_image

def ingest_image(image_path, session_id: str):
    source_name = os.path.basename(image_path)
    print(f"[*] Processing image: {source_name} (session: {session_id})")
    try:
        # Validate image
        with Image.open(image_path) as img:
            img.verify()
        print(f"[+] Image validated: {source_name}")
        
        embedding = embed_image(image_path)
        print("[+] Embedding created")
    except Exception as e:
        import traceback
        print(f"[-] Image embedding failed for {image_path}: {str(e)}")
        traceback.print_exc()
        return

    collection = get_image_collection()

    try:
        collection.add(
            ids=[str(uuid.uuid4())],
            embeddings=[embedding],
            documents=[image_path],
            metadatas=[{"source": source_name, "session_id": session_id, "type": "image", "timestamp": str(time.time())}]
        )
        print("[+] Stored in DB")
        
        from session_store import session_store
        session_store.update_stats(session_id)
        print("[+] Updated session stats from Chroma")
    except Exception as e:
        print(f"[-] Image add to Chroma failed: {str(e)}")
        return

    print(f"[*] Image processing complete for session {session_id}")
