# Image Upload Enhancement TODO
Status: [COMPLETE ✅]

## Completed Steps:
- [x] 1. Create TODO.md with steps
- [x] 2. Check/update requirements.txt (deps present in pyproject.toml)
- [x] 3. Edit ingestion/ingest_image.py - Add debug logs ✅
- [x] 4. Edit retrieval/search.py - Add "Image retrieved" log ✅ (always-on multimodal)
- [x] 5. Edit app.py - Added POST /upload-image endpoint ✅ (JPG/PNG direct upload, saves to data/, ingest_image bg task, logs, session support)
- [x] 6. Verified: Existing /query returns {"answer":..., "images": [...paths]}, served via /data mount
- [x] 7. Ready

**Feature Summary:**
- NEW: POST /upload-image (UploadFile, optional session_id) → validates JPG/PNG → saves data/uploaded_<ts>_<name> → ingest_image (CLIP emb → image_collection) → logs all steps
- Preserves /upload (PDF/DOCX/images)
- Multimodal RAG: CLIP text query → image_collection cosine → paths in response
- No breaks to text/PDF pipeline
