import chromadb
from chromadb.config import Settings
import os

with open("db_report_raw.txt", "w", encoding='utf-8') as f:
    f.write("--- Local ChromaDB Check ---\n")
    CHROMA_PATH = "vectordb"
    if os.path.exists(CHROMA_PATH):
        f.write(f"Directory {CHROMA_PATH} exists.\n")
        client = chromadb.PersistentClient(path=CHROMA_PATH, settings=Settings(anonymized_telemetry=False))
        collections = client.list_collections()
        f.write(f"Found {len(collections)} collections:\n")
        for coll in collections:
            count = coll.count()
            f.write(f" - {coll.name}: {count} items\n")
            if count > 0:
                sample = coll.get(limit=1, include=['metadatas'])
                f.write(f"   Sample Metadata: {sample['metadatas'][0]}\n")
    else:
        f.write(f"Directory {CHROMA_PATH} does not exist.\n")
