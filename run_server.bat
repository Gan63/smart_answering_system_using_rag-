@echo off
echo Starting Multimodal RAG Server...
cd /d "c:/Users/Ganesh/Desktop/multimodal_rag"
echo Server directory: %CD%
echo.
echo 🚀 Starting on http://localhost:8000 ^(Ctrl+C to stop^)
echo.
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
pause

