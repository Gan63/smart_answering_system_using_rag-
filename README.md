# Multimodal RAG with Chroma Cloud Storage 🚀

## Quick Start
```
# 1. Chroma Cloud (Recommended)
set CHROMA_CLOUD_API_KEY=ch-...  # console.cloud.chroma.io → API Keys

# 2. Local fallback (no key needed)
# Uses ./vectordb/

# 3. Start server
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Open: http://localhost:8000
```

## Features
- **Docs**: PDF, DOCX (text + images extracted)
- **Images**: Embed captions/paths with CLIP
- **RAG**: Hybrid text+image retrieval
- **LLM**: OpenRouter (meta-llama/llama-3.1-8b-instruct) or Ollama local
- **Storage**: Chroma Cloud (pdf_vectors db) or local vectordb/
- **Sessions/Chats**: Persistent history

## Cloud Migration ✅
```
✅ database/chroma_client.py → CloudClient + local fallback
✅ Collections: text_collection, image_collection
✅ Tenant: 762b3932-4d8c-9b86-388d593c091f, DB: pdf_vectors
✅ Ingest → cloud console.cloud.chroma.io
```

## Test Pipeline
```
curl -X POST -F "file=@data/SMB_University_120307_Networking_Fundamentals.pdf" http://localhost:8000/upload
# Note session_id → query:
curl -X POST http://localhost:8000/query -d '{"question":"What is networking?","session_id":"..."}'
```

## Troubleshooting
- **No cloud data?** Check `CHROMA_CLOUD_API_KEY` env var + server logs
- **Local fallback**: Logs "⚠️ No CHROMA_CLOUD_API_KEY - using local"
- **Health**: `/health`, `/llm-health`

## Architecture
```
Upload → Background Ingest (PDF/DOCX/Image)
     ↓
Embed (SentenceTransformer + CLIP) → Chroma Cloud/Local
     ↓
Query → Hybrid Retrieval → LLM (Vision if images)
     ↓
Response + Images/Sources
```

