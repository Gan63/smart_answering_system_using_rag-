import os
import time
import uvicorn
import traceback
import uuid
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from werkzeug.utils import secure_filename
import ollama  # NEW: Local LLM
from agent.planner import agent_query
from ingestion.ingest_pdf import ingest_pdf
from ingestion.ingest_docx import ingest_docx
from ingestion.ingest_image import ingest_image
from database.chroma_client import delete_session_data
from session_store import session_store
from utils.token_counter import count_tokens_from_response
from utils.session_manager import add_to_history, get_chat_history, get_session_stats
from utils.chat_store import chat_store
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

# =========================
# Globals
# =========================
llm_client = None
UPLOAD_FOLDER = "data"
OLLAMA_MODEL = "llama3.2"  # User pulls: ollama pull llama3.2

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - Ollama local (no API key!)
    global llm_client
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Test Ollama
    try:
        ollama.list()  # Ping
        llm_client = ollama  # Use global ollama.Client()
        print("✅ Ollama client ready! Model:", OLLAMA_MODEL)
    except Exception as e:
        print(f"⚠️ Ollama not available ({e}). Install ollama & run 'ollama pull llama3.2'")
        llm_client = None
    
    yield
    # Shutdown clean

# =========================
# 🚀 FASTAPI SETUP
# =========================
app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="project_ui"), name="static")
app.mount("/data", StaticFiles(directory="data", html=False), name="data")

# =========================
# 🤖 LLM FUNCTION - Ollama RAG (Text + Image captions)
# =========================
def ask_llm(text_context: str, images: List[Dict], question: str) -> str:
    if not llm_client:
        return "Ollama not available. Install Ollama and run 'ollama pull llama3.2'. RAG context ready:\n" + text_context[:500]
    
    # Image context from RAG (CLIP captions exist)
    image_context = ""
    if images:
        image_list = "\n".join([f"- {img.get('caption', 'Image')}: {img.get('path', '')}" for img in images[:3]])
        image_context = f"\nRelevant images:\n{image_list}"
    
    prompt = f"""Context from document:
{text_context}

{image_context}

Question: {question}

Answer accurately using ONLY the context above. If unclear, say so. Be concise."""

    try:
        response = llm_client.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}])
        return response['message']['content']
    except Exception as e:
        print(f"[LLM ERROR] {e}")
        return f"LLM error: {str(e)}. Context: {text_context[:200]}..."

# =========================
# 📦 REQUEST MODELS (unchanged)
# =========================
class AskRequest(BaseModel):
    question: str
    session_id: str
    top_k_text: int = 10
    top_k_image: int = 1

class ChatRequest(BaseModel):
    chat_id: Optional[str] = None
    message: str
    session_id: str
    file_name: Optional[str] = None
    user_id: str = "default"
    top_k_text: int = 10
    top_k_image: int = 1

# =========================
# 🌐 ROUTES (updated LLM calls)
# =========================
@app.get("/")
async def root():
    return FileResponse("project_ui/index.html")

@app.get("/login")
async def login():
    return FileResponse("project_ui/login.html")

@app.get("/health")
async def health():
    return {"status": "ok", "llm": "Ollama ready" if llm_client else "Ollama setup needed"}

@app.get("/test-llm")
async def test_llm():
    if not llm_client:
        return {"error": "Ollama not available"}
    try:
        resp = llm_client.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": "Say hello!"}])
        return {"status": "OK", "response": resp['message']['content']}
    except Exception as e:
        return {"error": str(e)}

@app.get("/favicon.ico")
async def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)

@app.post("/query")
async def query_endpoint(request: AskRequest):
    try:
        context = agent_query(request.question, request.session_id, request.top_k_text, request.top_k_image)
        
        if not context or not context.get('text_context'):
            return {"answer": "No relevant information found. Try after ingestion.", "images": [], "tokens": 0}

        text_context = context.get("text_context", "")
        images_list = context.get("images", [])
        answer = ask_llm(text_context, images_list, request.question)
        
        # Mock tokens (Ollama doesn't provide)
        tokens = {"prompt_tokens": len(text_context)//4, "completion_tokens": len(answer)//4, "total_tokens": 0}
        add_to_history(request.session_id, request.question, answer, context, images_list, tokens)
        
        return {"answer": answer, "context": context, "images": images_list, "tokens": tokens}
    except Exception as e:
        print(f"Query ERROR: {str(e)}")
        traceback.print_exc()
        return {"answer": f"Error: {str(e)}", "images": []}

# ... (upload, sessions, chats routes UNCHANGED - same as original)
@app.post("/upload")
async def upload(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    print(f"📤 Upload hit: {file.filename}")
    try:
        if not file:
            raise HTTPException(status_code=400, detail="No file uploaded")

        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        
        print(f"💾 Saving {filename}...")
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        
        session_id = str(uuid.uuid4())
        session_store.create_session(filename, session_id)
        
        ext = os.path.splitext(filename)[1].lower()
        
        def ingest_file():
            try:
                if ext == '.pdf':
                    ingest_pdf(file_path, session_id)
                elif ext == '.docx':
                    ingest_docx(file_path, session_id)
                elif ext in ['.png', '.jpg', '.jpeg', '.gif']:
                    ingest_image(file_path, session_id)
                else:
                    raise ValueError(f"Unsupported file type: {ext}")
                print(f"✅ Ingestion complete for {filename}")
            except Exception as e:
                print(f"❌ Ingestion failed for {filename}: {e}")

        print("🚀 Starting background ingestion...")
        background_tasks.add_task(ingest_file)
        
        return {"session_id": session_id, "filename": filename, "message": "Document uploaded. Processing..."}
    except Exception as e:
        print(f"[ERROR] Upload: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, setup=str(e))

@app.get("/sessions")
async def get_sessions():
    try:
        all_sessions = session_store.get_all_sessions()
        return {"sessions": [session.dict() for session in all_sessions]}
    except Exception as e:
        print(f"/sessions ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"sessions": [], "error": "Sessions unavailable"}

@app.get("/chats")
async def get_chats():
    try:
        chats = chat_store.get_chats()
        print(f"Serving {len(chats)} chats to frontend")
        return {"chats": [{"chat_id": c.chat_id, "title": c.title, "timestamp": c.timestamp, "message_count": len(c.messages), "last_message": c.messages[-1]["content"][:50] + "..." if c.messages else ""} for c in chats]}
    except Exception as e:
        print(f"/chats ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"chats": [], "error": "Chat store unavailable"}

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        context = agent_query(request.message, request.session_id, request.top_k_text, request.top_k_image)
        text_context = context.get("text_context", "") if context else ""
        images_list = context.get("images", []) if context else []

        if request.chat_id is None:
            request.chat_id = chat_store.create_chat(request.file_name or "Untitled", request.message, request.session_id, request.user_id)
            print(f"Created new chat {request.chat_id}")

        chat_store.append_message(request.chat_id, "user", request.message, [], [])
        chat_msgs = chat_store.get_chat(request.chat_id).messages

        messages = [{"role": "system", "content": f"RAG Context: {text_context}\nImages: {images_list}"}]
        for m in chat_msgs:
            messages.append({"role": m["role"], "content": m["content"]})

        if not llm_client:
            answer = "Ollama not ready. Context available."
        else:
            try:
                resp = llm_client.chat(model=OLLAMA_MODEL, messages=messages)
                answer = resp['message']['content']
            except Exception as e:
                print(f"Chat LLM error: {e}")
                answer = f"LLM temp error. Context: {text_context[:300]}..."

        chat_store.append_message(request.chat_id, "assistant", answer, [], [img['path'] for img in images_list])
        tokens = {"prompt_tokens": 100, "completion_tokens": len(answer)//4, "total_tokens": 200}  # Mock

        return {"response": answer, "chat_id": request.chat_id, "tokens": tokens, "images": images_list}
    except Exception as e:
        print(f"Chat error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    try:
        delete_session_data(session_id)
        return {"message": f"Session {session_id} deleted."}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("app_ollama:app", host="0.0.0.0", port=8000, reload=True)
