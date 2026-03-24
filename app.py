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
from openai import OpenAI
from agent.planner import agent_query
from ingestion.ingest_pdf import ingest_pdf
from ingestion.ingest_docx import ingest_docx
from ingestion.ingest_image import ingest_image
from database.chroma_client import delete_session_data
from session_store import session_store
from utils.token_counter import count_tokens_from_response
from utils.session_manager import add_to_history, get_chat_history, get_session_stats
from utils.chat_store import chat_store
from typing import Optional
from contextlib import asynccontextmanager

# =========================
# Globals
# =========================
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
    yield

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
# 🤖 LLM FUNCTION - Smart RAG Assistant (EXACT SPEC)
# =========================
def ask_llm(text_context: str, images: list, question: str):
    """
    Smart RAG Assistant - follows exact rules from task.
    """
    try:
        image_keywords = ["show image", "diagram", "figure", "visual"]
        question_lower = question.lower()
        show_images = any(keyword in question_lower for keyword in image_keywords)

        messages = []

        # Conditional image context (JSON ready)
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
        
        messages.append({"role": "user", "content": prompt_text})

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

# =========================
# 📦 REQUEST MODELS
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
# 🌐 ROUTES
# =========================
@app.get("/")
async def root():
    return FileResponse("project_ui/index.html")

@app.get("/login")
async def login():
    return FileResponse("project_ui/login.html")

@app.get("/health")
async def health():
    print("Health check OK")
    return {"status": "ok"}

@app.get("/favicon.ico")
async def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)

@app.post("/query")
async def query_endpoint(request: AskRequest):
    try:
        context = agent_query(request.question, request.session_id, request.top_k_text, request.top_k_image)
        
        if not context or not context.get('text_context'):
            return {"answer": "No relevant information found in the document. Try rephrasing your question after ingestion completes.", "error": "No context", "images": [], "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}

        text_context = context.get("text_context", "")
        images_list = context.get("images", [])
        answer = ask_llm(
            text_context=text_context,
            images=images_list,
            question=request.question
        )
        tokens_response = llm_client.chat.completions.create(
            model="meta-llama/llama-3-8b-instruct",
            messages=[{"role": "user", "content": f"""Context:
{text_context}

Question: {request.question}"""}],
            temperature=0.1
        )
        tokens = count_tokens_from_response(tokens_response)
        add_to_history(request.session_id, request.question, answer, context, images_list, tokens)
        return {
            "answer": answer,
            "context": context,
            "images": images_list,
            "tokens": tokens
        }
    except Exception as e:
        print(f"DEBUG FULL ERROR in query: {str(e)}")
        traceback.print_exc()
        return {"answer": f"Server error: {str(e)}", "error": str(e), "images": []}

@app.post("/upload")
async def upload(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    print(f"📤 Upload hit: {file.filename}")
    try:
        if not file:
            raise HTTPException(status_code=400, detail="No file uploaded")

        content_type = file.content_type.lower() if file.content_type else ''
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        
        print(f"💾 Saving {filename} (content_type: {content_type})")
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        
        session_id = str(uuid.uuid4())
        session_store.create_session(filename, session_id)
        
        def ingest_file():
            try:
                print(f"🔍 Dispatching {filename}: content_type='{content_type}'")
                if content_type == 'application/pdf':
                    print("📄 → ingest_pdf (unchanged)")
                    ingest_pdf(file_path, session_id)
                elif content_type in ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']:
                    print("🖼️ → ingest_image")
                    ingest_image(file_path, session_id)
                elif os.path.splitext(filename)[1].lower() == '.docx':
                    print("📝 → ingest_docx (ext fallback)")
                    ingest_docx(file_path, session_id)
                else:
                    raise ValueError(f"Unsupported: content_type='{content_type}', ext={os.path.splitext(filename)[1]}")
                print(f"✅ Ingestion complete for {filename}")
            except Exception as e:
                print(f"❌ Ingestion failed for {filename}: {e}")

        print(f"🚀 Starting background ingestion...")
        background_tasks.add_task(ingest_file)
        
        return {
            "session_id": session_id,
            "filename": filename,
            "content_type": content_type,
            "message": "File uploaded. Processing..."
        }
    except Exception as e:
        print(f"[ERROR] Upload: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-image")
async def upload_image(background_tasks: BackgroundTasks, file: UploadFile = File(...), session_id: str = None):
    print(f"🖼️ Direct image upload: {file.filename}")
    try:
        # Validate file type
        if not file:
            raise HTTPException(status_code=400, detail="No image uploaded")
        
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png']:
            raise HTTPException(status_code=400, detail="Only JPG/PNG supported")
        
        # Use provided session or create new
        if session_id is None:
            session_id = str(uuid.uuid4())
            session_store.create_session("image_upload", session_id)
        
        # Save temp file for ingest_image (expects path)
        filename = secure_filename(file.filename)
        image_path = os.path.join(UPLOAD_FOLDER, f"uploaded_{int(time.time())}_{filename}")
        with open(image_path, "wb") as buffer:
            buffer.write(await file.read())
        
        print(f"💾 Image saved: {image_path}")
        
        def process_image():
            try:
                ingest_image(image_path, session_id)
            except Exception as e:
                print(f"❌ Image processing failed: {e}")
        
        background_tasks.add_task(process_image)
        
        return {
            "session_id": session_id,
            "filename": filename,
            "image_path": f"/data/{filename}",
            "message": "Image uploaded and processing..."
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Image upload: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history/{session_id}")
async def get_history(session_id: str):
    try:
        history = get_chat_history(session_id)
        stats = get_session_stats(session_id)
        if history:
            return {
                "history": [msg.dict() for msg in history],
                "stats": stats or {}
            }
        return {"history": [], "stats": stats or {}}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions")
async def get_sessions():
    try:
        all_sessions = session_store.get_all_sessions()
        return {
            "sessions": [session.dict() for session in all_sessions]
        }
    except Exception as e:
        print(f"/sessions ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"sessions": [], "error": "Sessions unavailable"}

@app.get("/chats")
async def get_chats():
    """List all chats for user."""
    try:
        chats = chat_store.get_chats(user_id="default")
        print(f"Serving {len(chats)} chats to frontend")
        return {
            "chats": [
                {
                    "chat_id": c.chat_id,
                    "title": c.title,
                    "timestamp": c.timestamp,
                    "message_count": len(c.messages),
                    "last_message": c.messages[-1]["content"][:50] + "..." if c.messages else ""
                }
                for c in chats
            ]
        }
    except Exception as e:
        print(f"/chats ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"chats": [], "error": "Chat store unavailable"}

@app.get("/history/{user_id}")
async def get_user_history(user_id: str):
    """Get chat history for specific user."""
    try:
        chats = chat_store.get_chats(user_id="default")
        return {
            "user_id": user_id,
            "chats": [
                {
                    "chat_id": c.chat_id,
                    "title": c.title,
                    "timestamp": c.timestamp,
                    "message_count": len(c.messages)
                }
                for c in chats
            ]
        }
    except Exception as e:
        traceback.print_exc()
        return {"chats": [], "error": "Chat history unavailable"}

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        # RAG context
        context = agent_query(request.message, request.session_id, request.top_k_text, request.top_k_image)
        if not context or not context.get('text_context'):
            context = {"text_context": "", "images": []}

        text_context = context.get("text_context", "")
        images_list = context.get("images", [])
        sources = context.get("text_results", [{}]) if "text_results" in context else []

        # Chat logic
        if request.chat_id is None:
            # New chat - create with user message
            request.chat_id = chat_store.create_chat(
                request.file_name or "Untitled", 
                request.message, 
                request.session_id, 
                request.user_id
            )
            print(f"Created new chat {request.chat_id} with title from file: {request.file_name or 'Untitled'}")
        else:
            chat_store.append_message(request.chat_id, "user", request.message, [], [])
            # Load for LLM - STRICT validation
            existing = chat_store.get_chat(request.chat_id)
            if not existing:
                raise HTTPException(status_code=404, detail="Chat not found")

        # LLM with full conversation memory
        chat_msgs = chat_store.get_chat(request.chat_id).messages
        messages = [{"role": "system", "content": f"Use this context: {text_context}\nImages: {images_list}"}]
        for m in chat_msgs:
            messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": request.message})

        response = llm_client.chat.completions.create(
            model="meta-llama/llama-3-8b-instruct",
            messages=messages,
            temperature=0.1
        )
        answer = response.choices[0].message.content

        # Store assistant response (sources/images)
        source_paths = [s.get('document', '') for s in sources if 'document' in s]
        chat_store.append_message(request.chat_id, "assistant", answer, source_paths, [img['path'] for img in images_list])

        tokens = count_tokens_from_response(response)

        return {
            "response": answer,
            "chat_id": request.chat_id,
            "tokens": tokens,
            "sources": source_paths,
            "images": images_list
        }
    except Exception as e:
        print(f"Chat error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/{chat_id}")
async def get_full_chat(chat_id: str):
    try:
        chat = chat_store.get_chat(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        return {"chat": chat.dict()}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/chat/{chat_id}")
async def delete_chat(chat_id: str):
    try:
        success = chat_store.delete_chat(chat_id)
        if success:
            print(f"Deleted chat {chat_id}")
            return {"message": f"Chat {chat_id} deleted successfully."}
        else:
            raise HTTPException(status_code=404, detail="Chat not found")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete_chat/{chat_id}")
async def delete_chat_new(chat_id: str):
    """
    NEW endpoint for delete chat as per task requirements
    """
    try:
        success = chat_store.delete_chat(chat_id)
        if success:
            print(f"Deleted chat {chat_id} via /delete_chat")
            return {"success": True, "message": f"Chat {chat_id} deleted successfully."}
        else:
            raise HTTPException(status_code=404, detail="Chat not found")
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    try:
        delete_session_data(session_id)
        return {"message": f"Session {session_id} deleted."}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

