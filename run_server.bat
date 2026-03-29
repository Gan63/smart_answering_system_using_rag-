@echo off
cd /d "c:\Users\Ganesh\Desktop\multimodal_rag"
call .venv\Scripts\activate
echo 🚀 Starting optimized Multimodal RAG server...
uvicorn app_fixed_startup:app --host 0.0.0.0 --port 8000 --reload
pause
