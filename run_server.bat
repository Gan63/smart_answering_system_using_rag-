@echo off
call .venv\Scripts\activate.bat
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
pause
