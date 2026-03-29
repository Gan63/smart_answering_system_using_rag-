# Cloud + Local ChromaDB Hybrid Setup
Status: Planned

1. [ ] Set CHROMA_CLOUD_API_KEY env var (get from https://cloud.trychroma.com)
2. [ ] Update chroma_client.py: Prefer cloud if key set, fallback local
3. [ ] Test cloud mode with inspect_db_fixed.py
4. [ ] Add sync logic if needed (cloud <-> local)

Current: Local works perfectly.
