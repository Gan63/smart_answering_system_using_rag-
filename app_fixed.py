import os
import time
import uvicorn
import traceback
import uuid
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from werkzeug.utils import secure_filename
from openai import OpenAI
from agent.planner import agent_query
from ingestion.ingest_pdf import ingest_pdf
from ingestion.ingest_docx import ingest_docx
from ingestion.ingest_image import ingest_image
from database.chroma_client import delete_session_data
from session_store import session_store
from utils.token_counter import count_tokens_from_response
from utils.session_manager import add_to_history, get_chat_history, get_session_stats
from utils.chat_backend import (
    init_json, load_data, save_data, get_chats, get_chat, 
    create_chat, append_message, delete_chat
)
from typing import Optional, List
from contextlib import asynccontextmanager

# Globals
llm_client = None
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
UPLOAD_FOLDER = "data"

@asynccontextmanager
async def lifespan(app: FastAPI):
    global llm_client
    if not OPENROUTER_API_KEY:
        raise ValueError("[X] Please set OPENROUTER_API_KEY")

    llm_client = OpenAI(
        api_key="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",
        base_url="https://openrouter.ai/api/v1"
    )
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    init_json()  # Initialize chat_history.json
    yield

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

def ask_llm(text_context: str, images: list, question: str):
    image_keywords = ["show image", "diagram", "figure", "visual"]
    question_lower = question.lower()
    show_images = any(keyword in question_lower for keyword in image_keywords)     
    try:
        image_context_str = ""
        if show_images and images:
            image_list = []
            for img in images[:3]:
                url = img["path"].replace("data/", "/data/")
                caption = img.get("caption", "Relevant image")
                image_list.append(f'  {{"url": "{url}", "caption": "{caption}"}}')
            image_context_str = f"""Available Images (use exactly):
[
{chr(10).join(image_list)}
]"""

        prompt_text = f"""Context:
{text_context}

{image_context_str}

Question: {question}"""
        
        messages = [{"role": "user", "content": prompt_text}]

        model = "meta-llama/llama-3-8b-instruct"
        
        response = llm_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[ERROR] LLM: {e}")
        raise

class ChatRequest(BaseModel):
    chat_id: Optional[str] = None
    message: str
    session_id: Optional[str] = None  # Optional for pure chat
    file_name: Optional[str] = None
    top_k_text: int = 10
    top_k_image: int = 1

@app.get("/")
async def root():
    return FileResponse("project_ui/index.html")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/chats")
async def api_get_chats():
    return {"chats": get_chats()}

@app.get("/chat/{chat_id}")
async def api_get_chat(chat_id: str):
    chat = get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"chat": chat}

@app.delete("/chat/{chat_id}")
async def api_delete_chat(chat_id: str):
    if delete_chat(chat_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Chat not found")

@app.post("/chat")
async def api_post_chat(request: ChatRequest):
    try:
        # STRICT CHAT MATCHING
        chats = load_data()
        chat = next((c for c in chats if c["chat_id"] == request.chat_id), None)
        
        # NEW CHAT if none
        if not chat:
            chat_id = create_chat(request.file_name or "New Chat")
            chat = get_chat(chat_id)  # Reload
            print(f"Created new chat {chat_id}")
        else:
            chat_id = chat["chat_id"]
        
        # APPEND USER MESSAGE ONLY TO THIS CHAT
        sources = []
        images = []
        if request.session_id:
            # RAG if session provided
            context = agent_query(request.message, request.session_id, request.top_k_text, request.top_k_image)
            if context:
                sources = context.get("text_results", [{}])
                images = context.get("images", [])
            text_context = context.get("text_context", "") if context else ""
        else:
            text_context = ""
        
        append_message(chat_id, "user", request.message)
        
        # GENERATE REPLY (RAG ONLY, NO CHAT HISTORY IN LLM)
        reply = ask_llm(text_context, images, request.message)
        source_paths = [s.get('document', '') for s in sources]
        img_paths = [img['path'] for img in images]
        append_message(chat_id, "assistant", reply, source_paths, img_paths)
        
        # NEVER OVERWRITE FULL FILE - chats list saved atomically
        tokens = len(reply.split())
        
        return {
            "chat_id": chat_id,
            "reply": reply,
            "tokens": tokens
        }
    except Exception as e:
        print(f"Chat error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Keep existing RAG/upload endpoints unchanged
class AskRequest(BaseModel):
    question: str
    session_id: str
    top_k_text: int = 10
    top_k_image: int = 1

@app.post("/query")
async def query_endpoint(request: AskRequest):
    try:
        context = agent_query(request.question, request.session_id, request.top_k_text, request.top_k_image)
        
        if not context or not context.get('text_context'):
            return {"answer": "No relevant information found.", "images": [], "tokens": 0}

        text_context = context.get("text_context", "")
        images_list = context.get("images", [])
        answer = ask_llm(text_context, images_list, request.question)
        
        add_to_history(request.session_id, request.question, answer, context, images_list, {"total_tokens": 0})
        return {"answer": answer, "context": context, "images": images_list, "tokens": {"total_tokens": 0}}
    except Exception as e:
        traceback.print_exc()
        return {"answer": f"Error: {str(e)}"}

@app.post("/upload")
async def upload(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    try:
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        
        session_id = str(uuid.uuid4())
        session_store.create_session(filename)
        
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
                    print(f"Unsupported file type: {ext}")
            except Exception as e:
                print(f"Ingestion failed: {e}")
        
        background_tasks.add_task(ingest_file)
        print(f"Upload success: {filename}, session: {session_id}")
        return {"session_id": session_id, "filename": filename}
    except Exception as e:
        print(f"Upload error: {e}")

@app.get("/history/{session_id}")
async def get_history(session_id: str):
    history = get_chat_history(session_id)
    stats = get_session_stats(session_id)
    return {"history": [msg.dict() for msg in history] if history else [], "stats": stats or {}}

@app.get("/sessions")
async def get_sessions():
    return {"sessions": [s.dict() for s in session_store.get_all_sessions()]}

@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    delete_session_data(session_id)
    return {"message": "Session deleted"}

if __name__ == "__main__":
    uvicorn.run("app_fixed:app", host="0.0.0.0", port=8000, reload=True)

