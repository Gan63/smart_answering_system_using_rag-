from utils.auth import register_google_user
from utils.auth import get_user_by_google_id
import os
import time
import uvicorn
import traceback
import uuid
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from werkzeug.utils import secure_filename
import base64
from openai import OpenAI
from openai import APIConnectionError, AuthenticationError
from agent.planner import agent_query
from ingestion.ingest_pdf import ingest_pdf
from ingestion.ingest_docx import ingest_docx
from ingestion.ingest_image import ingest_image
from database.chroma_client import delete_session_data
from database.db_config import get_db_connection, test_connection
from session_store import session_store
from utils.token_counter import count_tokens_from_response
from utils.session_manager import add_to_history, get_chat_history, get_session_stats
from utils.chat_store import chat_store
from utils.ai_router import AIRouter
from utils.hybrid_router import HybridRouter, detect_mode
from utils.auth import User, get_current_active_user, authenticate_user, create_access_token, register_user, update_last_login
from typing import List, Optional
from contextlib import asynccontextmanager
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Form, Body
from datetime import timedelta
import secrets

llm_client = None
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
UPLOAD_FOLDER = "data"

@asynccontextmanager
async def lifespan(app: FastAPI):
    global llm_client
    
    # Use environment variable for security
    api_key = os.getenv("OPENROUTER_API_KEY")
    
    if not api_key:
        print("[WARNING] OPENROUTER_API_KEY not found in environment. Using development fallback.")
        api_key = "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"

    llm_client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1"
    )
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    print(f"[INFO] LLM client initialized with API key: {api_key[:20]}...")
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

def ask_llm(text_context: str, images: list, question: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            image_keywords = ["show image", "diagram", "figure", "visual"]
            question_lower = question.lower()
            show_images = any(keyword in question_lower for keyword in image_keywords)

            messages = []

            image_context_str = ""
            if show_images and images:
                seen_urls = set()
                unique_images = []
                for img in images:
                    if img["path"] not in seen_urls:
                        seen_urls.add(img["path"])
                        unique_images.append(img)
                
                image_list = []
                for img in unique_images[:3]:
                    url = img["path"].replace("data/", "/data/")
                    caption = img.get("caption", "Relevant image")
                    image_list.append(f'  {{"url": "{url}", "caption": "{caption}"}}')
                image_context_str = f"""Available Images (use exactly):
[
{chr(10).join(image_list)}
]"""

            prompt_text = f"""You are a helpful AI assistant. You answer based on the provided context when applicable.

IDENTITY:
- You are a Smart Multimodal RAG Assistant.
- You were created by a talented developer and Code Assistant creator (Ganesh).
- Your work includes reading, understanding, and extracting information from uploaded files like PDFs, Word documents, and images.
- Your process involves: searching the given documents to find relevant text and images that match the user's query, analyzing this extracted context, and finally synthesizing a precise and accurate response based strictly on the uploaded content.

Context:
{text_context}

{image_context_str}

CRITICAL RULES:
1. When the user asks a factual question about the document, you MUST answer ONLY using the Context and Images provided.
2. If the user asks a factual document question and the answer is NOT explicitly available in the Context, you MUST say "I cannot find the answer to this in the uploaded documents." DO NOT guess.
3. If giving an image, use the exact markdown provided. For each image, strictly use this format:
![caption](url)
**Image Description:** <detailed description based on context>
Never output duplicate images.
4. You may engage in standard conversational greetings and general reasoning.

Question: {question}"""
            
            messages.append({"role": "user", "content": prompt_text})

            model = "meta-llama/llama-3.1-8b-instruct"

            print(f"[INFO] LLM call attempt {attempt + 1}/{max_retries}")
            
            response = llm_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.1
            )
            print(f"[INFO] LLM success on attempt {attempt + 1}")
            return response.choices[0].message.content
        
        except APIConnectionError as e:
            print(f"[WARN] LLM connection error (attempt {attempt + 1}): {str(e)}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"[INFO] Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            preview = text_context[:500] + "..." if text_context else "No context"
            fallback = f"""❌ LLM SERVICE OFFLINE (Connection error: DNS/Internet issue)

Please check:
1. Internet connection: ping google.com
2. DNS resolution: ping openrouter.ai
3. Firewall/VPN blocking OpenRouter

Retrieved {len(images)} image(s) and text context available:
{preview}

**Answer**: Unable to generate response due to network failure."""
            print("[INFO] LLM offline fallback used")
            return fallback
            
        except AuthenticationError as e:
            print(f"[ERROR] LLM auth error: {str(e)}")
            return f"❌ API KEY INVALID: {str(e)}"
        
        except Exception as e:
            print(f"[ERROR] LLM unexpected error (attempt {attempt + 1}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return f"❌ LLM ERROR: {str(e)}"
    
    return "❌ Max retries exceeded"

def is_image_query(question: str) -> bool:
    """Detect if the user is asking for images, diagrams, visuals, or display."""
    image_keywords = [
        "image", "images", "picture", "pictures", "photo", "photos",
        "diagram", "diagrams", "figure", "figures", "chart", "charts",
        "visual", "visuals", "display", "show me", "show image",
        "illustration", "graph", "graphs", "screenshot", "plot", "plots",
        "infographic", "map", "maps", "schematic", "schematics",
        "table image", "draw", "drawing", "visualize", "visualise"
    ]
    q_lower = question.lower()
    return any(kw in q_lower for kw in image_keywords)


class AskRequest(BaseModel):
    question: str
    session_id: str
    top_k_text: int = 10
    top_k_image: int = 5

class ChatRequest(BaseModel):
    chat_id: Optional[str] = None
    message: str
    session_id: Optional[str] = None
    file_name: Optional[str] = None
    user_id: str = "default"
    top_k_text: int = 10
    top_k_image: int = 5

class HybridChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    chat_id: Optional[str] = None
    file_name: Optional[str] = None
    user_id: str = "default"
    top_k_text: int = 10
    top_k_image: int = 5
    screenshot: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str

class GoogleLoginRequest(BaseModel):
    id_token: str

@app.get("/")
async def root():
    return FileResponse("project_ui/index.html")

@app.get("/modern")
async def modern_ui():
    return FileResponse("project_ui/modern_chat.html")

@app.get("/dashboard")
async def dashboard_page():
    return FileResponse("project_ui/dashboard.html")

@app.get("/login")
async def login_page():
    return FileResponse("project_ui/login.html")

@app.get("/health")
async def health():
    print("Health check OK")
    return {"status": "ok", "llm_available": True}

@app.get("/llm-health")
async def llm_health():
    try:
        test_response = llm_client.chat.completions.create(
            model="meta-llama/llama-3.1-8b-instruct",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5
        )
        return {"status": "ok", "llm_connected": True, "model": "meta-llama/llama-3.1-8b-instruct"}
    except Exception as e:
        return {"status": "error", "llm_connected": False, "error": str(e)[:200]}

@app.get("/db-health")
async def db_health():
    """Check MySQL cloud database connectivity — useful after deploying to Render."""
    result = test_connection()
    status_code = 200 if result["connected"] else 503
    return JSONResponse(content=result, status_code=status_code)

@app.get("/favicon.ico")
async def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)

# --- AUTH ENDPOINTS ---

@app.post("/api/auth/register")
async def api_register(request: RegisterRequest):
    try:
        user_data = register_user(request.full_name, request.email, request.password)
        access_token = create_access_token(data={"sub": request.email})
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_data
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Register error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/auth/login")
async def api_login(request: LoginRequest):
    user = authenticate_user(request.email, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    update_last_login(request.email)
    access_token = create_access_token(data={"sub": request.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "full_name": user["full_name"],
            "email": user["email"]
        }
    }

@app.post("/api/auth/google")
async def api_google_login(request: GoogleLoginRequest):
    """
    Handles Google OAuth2 token verification and user login/registration.
    Accepts a Google OAuth2 id_token from the frontend.
    """
    import httpx
    
    CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    
    if not CLIENT_ID:
        raise HTTPException(
            status_code=503, 
            detail="Google Sign-In is not configured. Please set GOOGLE_CLIENT_ID in your environment variables."
        )
    
    # Verify the id_token with Google's tokeninfo endpoint
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": request.id_token}
            )
        
        if response.status_code != 200:
            print(f"❌ Tokeninfo error: {response.text}")
            raise HTTPException(status_code=401, detail="Invalid Google token")
        
        idinfo = response.json()
        
        print("\n" + "="*50)
        print(f"🔍 [DEBUG] Full Google Auth Payload:")
        print(idinfo)
        print("="*50 + "\n")
        
        # Verify the audience matches our client ID
        if idinfo.get("aud") != CLIENT_ID:
            print(f"❌ Token audience mismatch: {idinfo.get('aud')} != {CLIENT_ID}")
            raise HTTPException(status_code=401, detail="Token audience mismatch")
            
        if "email" not in idinfo:
            print("❌ Scope Issue: 'email' field missing in Google Auth Response.")
            raise HTTPException(status_code=400, detail="Missing email scope. Ensure Google Cloud Console has People API and OAuth consent configured for email.")
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Google Token Verification Error: {e}")
        raise HTTPException(status_code=401, detail="Failed to verify Google token")

    google_id = idinfo.get('sub')
    email = idinfo.get('email')
    
    if not email:
        raise HTTPException(status_code=400, detail="No email associated with this Google Account")
        
    name = idinfo.get('name', email.split('@')[0])
    picture = idinfo.get('picture')

    user = get_user_by_google_id(google_id)
    if not user:
        # Check if user exists by email but no google_id
        from utils.auth import get_user_by_email
        user = get_user_by_email(email)
        if user:
            # Link existing account
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET google_id = %s, pfp_url = %s WHERE id = %s", (google_id, picture, user['id']))
            conn.commit()
            cursor.close()
            conn.close()
        else:
            # Register new user
            user = register_google_user(name, email, google_id, picture)
    
    access_token = create_access_token(data={"sub": email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "full_name": name,
            "email": email,
            "pfp_url": picture
        }
    }

@app.get("/api/auth/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

@app.post("/query")
async def query_endpoint(request: AskRequest):
    try:
        context = agent_query(request.question, request.session_id, request.top_k_text, request.top_k_image)
        
        if not context or not context.get('text_context'):
            context = {"text_context": "", "images": []}

        text_context = context.get("text_context", "")
        image_paths = context.get("image_paths", [])
        router = AIRouter(llm_client)
        if image_paths:
            result = router.generate_response(request.question, context, image_paths)
            answer = result["answer"]
            image_desc = result["image_desc"]
            used_vision = result["used_vision"]
            tokens = result.get("tokens", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
        else:
            answer = ask_llm(
                text_context=text_context,
                images=[],
                question=request.question
            )
            image_desc = None
            used_vision = False
            tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            try:
                tokens_response = llm_client.chat.completions.create(
                    model="meta-llama/llama-3.1-8b-instruct",
                    messages=[{"role": "user", "content": f"""Context: {text_context[:1000]}\nQ: {request.question}"""}],
                    temperature=0.1
                )
                tokens = count_tokens_from_response(tokens_response)
            except:
                tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        
        images_list = [{"path": p.split(" | ")[0] if " | " in p else p} for p in context.get("image_paths", [])]
        add_to_history(request.session_id, request.question, answer, context, images_list, tokens)
        return {
            "answer": answer,
            "image_desc": image_desc,
            "used_vision": used_vision,
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
        
        from utils.session_manager import get_session_stats
        stats = get_session_stats(session_id) or {}
        
        return {
            "session_id": session_id,
            "filename": filename,
            "chunk_count": stats.get('chunk_count', 0),
            "vector_count": stats.get('vector_count', 0),
            "content_type": content_type,
            "message": "File uploaded. Processing in background..."
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

@app.get("/api/session/{session_id}")
async def get_session_stats_api(session_id: str):
    from utils.session_manager import get_session_stats
    stats = get_session_stats(session_id) or {}
    return {
        "session_id": session_id,
        "chunk_count": stats.get('chunk_count', 0),
        "vector_count": stats.get('vector_count', 0),
        "message_count": stats.get('message_count', 0)
    }

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
                    "file_name": getattr(c, 'file_name', None),
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
    """Legacy redirect to new Hybrid Chat logic."""
    try:
        hybrid_req = HybridChatRequest(
            message=request.message,
            session_id=request.session_id,
            chat_id=request.chat_id,
            file_name=request.file_name,
            user_id=request.user_id,
            top_k_text=request.top_k_text,
            top_k_image=request.top_k_image
        )
        return await hybrid_chat_endpoint(hybrid_req)
    except Exception as e:
        print(f"Chat redirect error: {str(e)}")
        import traceback
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

class RenameRequest(BaseModel):
    title: str

@app.patch("/chat/{chat_id}/rename")
async def rename_chat(chat_id: str, request: RenameRequest):
    """Rename a specific chat history file name/title."""
    try:
        success = chat_store.rename_chat(chat_id, request.title)
        if success:
            return {"success": True, "message": f"Chat renamed to {request.title}"}
        else:
            raise HTTPException(status_code=404, detail="Chat not found")
    except Exception as e:
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

# ─── HYBRID CHAT ENDPOINT ───
@app.post("/api/hybrid-chat")
async def hybrid_chat_endpoint(request: HybridChatRequest):
    """
    Intelligent hybrid endpoint: auto-detects RAG / Code / Hybrid mode.
    Returns structured responses with mode metadata.
    """
    try:
        # 1. Retrieve context if a session exists
        text_context = ""
        image_paths = []
        sources = []
        if request.session_id:
            context = agent_query(
                request.message, request.session_id,
                request.top_k_text, request.top_k_image
            )
            if context:
                text_context = context.get("text_context", "")
                image_paths = context.get("image_paths", [])
                sources = [s.get("document", "") for s in context.get("text_results", []) if "document" in s]

        # 1.5 Handle immediate screenshot if provided
        if request.screenshot:
            try:
                # Remove header if exists
                screenshot_data = request.screenshot
                if "," in screenshot_data:
                    screenshot_data = screenshot_data.split(",")[1]
                
                img_bytes = base64.b64decode(screenshot_data)
                filename = f"capture_{int(time.time())}.png"
                filepath = os.path.join("data", "debug_screenshots", filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, "wb") as f:
                    f.write(img_bytes)
                
                # Add to image_paths for vision analysis
                # Format expected by AIRouter: "path | caption"
                image_paths.append(f"{filepath} | Immediate Screen Capture")
                print(f"[HYBRID CHAT] Integrated immediate screenshot for analysis: {filepath}")
            except Exception as se:
                print(f"[ERROR] Failed to integrate screenshot: {se}")

        # 2. Detect mode
        has_context = bool(text_context and text_context.strip())
        mode = detect_mode(request.message, has_context)
        print(f"[HYBRID CHAT] Message: '{request.message[:50]}...' | Mode: {mode} | Context: {has_context}")

        # 3. Chat history for continuity
        chat_history = []
        if request.chat_id:
            chat = chat_store.get_chat(request.chat_id)
            if chat:
                chat_history = chat.messages[-6:]  # last 6 turns

        # 4. If we have images (from RAG or immediate capture), use vision analysis
        used_vision = False
        image_desc = None
        if image_paths:
            router = AIRouter(llm_client)
            vision_ctx = {
                "text_context": text_context,
                "image_paths": image_paths,
                "text_sources": sources,
            }
            vision_result = router.generate_response(request.message, vision_ctx, image_paths)
            text_context += f"\n\n[Vision Analysis]: {vision_result.get('image_desc', '')}"
            image_desc = vision_result.get("image_desc")
            used_vision = True

        # 5. Route through HybridRouter
        hybrid = HybridRouter(llm_client)
        result = hybrid.route(
            user_input=request.message,
            text_context=text_context,
            chat_history=chat_history,
        )

        # 5.5 Handle Image Generation if mode is IMAGE
        generated_image_b64 = None
        if result["mode"] == "IMAGE":
            print(f"[HYBRID CHAT] Image generation intent detected.")
            # If the answer is very short, it's probably a question/clarification, not a prompt
            if len(result["answer"]) > 20: 
                from utils.ai_router import AIRouter
                print(f"[HYBRID CHAT] Generating image with prompt: {result['answer'][:100]}...")
                try:
                    router = AIRouter(llm_client)
                    generated_image_b64 = router.generate_image(result["answer"])
                    if generated_image_b64:
                        result["answer"] = f"🎨 **Generated Image**: {result['answer']}\n\nI have generated the image based on your request. You can see it below."
                    else:
                        result["answer"] = f"⚠️ **Generation Failed**: I created a prompt but the image service failed to respond. \n\n**Prompt**: {result['answer']}"
                except Exception as ex:
                    print(f"[ERROR] Image generation failed: {ex}")
                    result["answer"] = f"❌ **Error**: Image generation failed. \n\nDetails: {str(ex)}"
            else:
                print(f"[HYBRID CHAT] LLM asked a clarifying question instead of generating a prompt.")

        # 6. Manage chat persistence
        if request.chat_id is None:
            request.chat_id = chat_store.create_chat(
                request.file_name or "New Chat",
                request.message,
                request.session_id,
                request.user_id,
            )
        else:
            chat_store.append_message(request.chat_id, "user", request.message, [], [])

        # Build image list for response
        show_images = is_image_query(request.message) or result["mode"] == "IMAGE"
        images_list = []
        
        # Add generated image if successful
        if generated_image_b64:
            images_list.append({
                "path": f"data:image/png;base64,{generated_image_b64}",
                "caption": "Generated Image"
            })

        if show_images and image_paths:
            seen = set()
            for p in image_paths:
                path = p.split(" | ")[0].strip().replace("\\", "/").lstrip("/")
                url = "/" + path
                if url not in seen:
                    seen.add(url)
                    caption = p.split(" | ")[1].strip() if " | " in p else "Document image"
                    images_list.append({"path": url, "caption": caption})

        clean_image_paths = [im["path"] for im in images_list]
        chat_store.append_message(
            request.chat_id, "assistant", result["answer"], sources[:5], clean_image_paths
        )

        return {
            "response": result["answer"],
            "mode": result["mode"],
            "model": result["model"],
            "chat_id": request.chat_id,
            "used_vision": used_vision,
            "image_desc": image_desc,
            "sources": sources[:5],
            "images": images_list,
            "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
    except Exception as e:
        print(f"Hybrid chat error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/detect-mode")
async def detect_mode_endpoint(q: str, has_context: bool = False):
    """Lightweight mode-detection preview (no LLM call)."""
    mode = detect_mode(q, has_context)
    return {"mode": mode, "query": q}

@app.delete("/file/{session_id}")
async def delete_uploaded_file(session_id: str):
    """
    Delete an uploaded file and its vectors from ChromaDB.
    Removes the physical file from disk and clears the session from the in-memory store.
    """
    try:
        # Get session info before deleting
        session = session_store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        filename = session.filename

        # 1. Delete vectors from ChromaDB
        try:
            delete_session_data(session_id)
            print(f"[INFO] Deleted ChromaDB vectors for session {session_id}")
        except Exception as e:
            print(f"[WARN] Could not delete ChromaDB data for {session_id}: {e}")

        # 2. Remove physical file from disk
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        deleted_file = False
        if os.path.exists(file_path):
            os.remove(file_path)
            deleted_file = True
            print(f"[INFO] Deleted file: {file_path}")
        else:
            print(f"[WARN] File not found on disk: {file_path}")

        # Also delete any extracted images for this session (e.g. data/extracted_images/<session_id>_*.png)
        extracted_dir = os.path.join(UPLOAD_FOLDER, "extracted_images")
        if os.path.exists(extracted_dir):
            for img_file in os.listdir(extracted_dir):
                if session_id in img_file:
                    try:
                        os.remove(os.path.join(extracted_dir, img_file))
                        print(f"[INFO] Deleted extracted image: {img_file}")
                    except Exception as ie:
                        print(f"[WARN] Could not delete image {img_file}: {ie}")

        # 3. Remove from in-memory session store
        session_store.delete_session(session_id)

        return {
            "success": True,
            "session_id": session_id,
            "filename": filename,
            "file_deleted": deleted_file,
            "message": f"File '{filename}' and its data deleted successfully."
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] delete_uploaded_file: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/chats/all")
async def delete_all_chats():
    """Delete ALL chats permanently from the JSON database."""
    try:
        from utils.chat_store import save_data
        save_data([])
        print("[INFO] All chats deleted")
        return {"success": True, "message": "All chats deleted."}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/bulk_delete_chats")
async def bulk_delete_chats(chat_ids: List[str]):
    """Bulk delete chats by IDs. Expects JSON body [chat_id1, chat_id2...]"""
    try:
        from utils.chat_backend import bulk_delete_chats as backend_bulk_delete
        result = backend_bulk_delete(chat_ids)
        print(f"Bulk deleted {result['deleted']} chats")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/debug/screenshot")
async def save_debug_screenshot(request: Request):
    """
    Saves a screenshot from the frontend for debugging purposes.
    The filename is printed to the terminal to help logs context.
    """
    try:
        data = await request.json()
        image_data = data.get("image")
        if not image_data:
            raise HTTPException(status_code=400, detail="No image data provided")
        
        # Remove header if exists (e.g., data:image/png;base64,)
        header = ""
        if "," in image_data:
            header, image_data = image_data.split(",", 1)
            
        img_bytes = base64.b64decode(image_data)
        filename = f"debug_{int(time.time())}.png"
        filepath = os.path.join("data", "debug_screenshots", filename)
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(img_bytes)
            
        print(f"\n📸 [DEBUG] Screenshot captured and saved to: {filepath}")
        return {"success": True, "path": filepath, "filename": filename}
    except Exception as e:
        print(f"❌ [DEBUG] Failed to save screenshot: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
