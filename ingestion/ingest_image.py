import os
import uuid
from database.chroma_client import get_image_collection
from models.embedding_model import embed_image


def ingest_image(image_path, session_id: str):
    source_name = os.path.basename(image_path)
    embedding = embed_image(image_path)

    collection = get_image_collection()

    collection.add(
        ids=[str(uuid.uuid4())],
        embeddings=[embedding],
        documents=[image_path],
        metadatas=[{"source": source_name, "session_id": session_id}]
    )

    print("Image stored in ChromaDB")
