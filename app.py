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
import time
from openai import OpenAI
from openai import APIConnectionError, AuthenticationError
from agent.planner import agent_query
from ingestion.ingest_pdf import ingest_pdf
from ingestion.ingest_docx import ingest_docx
from ingestion.ingest_image import ingest_image
from database.chroma_client import delete_session_data
from session_store import session_store
from utils.token_counter import count_tokens_from_response
from utils.session_manager import add_to_history, get_chat_history, get_session_stats
from utils.chat_store import chat_store
from utils.ai_router import AIRouter
# from utils.auth import User, get_current_active_user
from typing import List, Optional
from contextlib import asynccontextmanager
from fastapi.security import HTTPBearer
from fastapi import Form
from datetime import timedelta
import secrets

llm_client = None
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
UPLOAD_FOLDER = "data"

@asynccontextmanager
async def lifespan(app: FastAPI):
    global llm_client
    
    # Use environment variable if set, otherwise fall back to hardcoded key
    api_key = OPENROUTER_API_KEY or "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"
    
    if not api_key:
        raise ValueError("[X] Please set OPENROUTER_API_KEY or provide a hardcoded key")

    llm_client = OpenAI(
        api_key="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",
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
                image_list = []
                for img in images[:3]:
                    url = img["path"].replace("data/", "/data/")
                    caption = img.get("caption", "Relevant image")
                    image_list.append(f'  {{"url": "{url}", "caption": "{caption}"}}')
                image_context_str = f"""Available Images (use exactly):
[
{chr(10).join(image_list)}
]"""

            prompt_text = f"""You are a helpful AI assistant. You answer based on the provided context when applicable.

Context:
{text_context}

{image_context_str}

CRITICAL RULES:
1. When the user asks a factual question about the document, you MUST answer ONLY using the Context and Images provided.
2. If the user asks a factual document question and the answer is NOT explicitly available in the Context, you MUST say "I cannot find the answer to this in the uploaded documents." DO NOT guess.
3. If giving an image, use the exact markdown provided.
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
    session_id: str
    file_name: Optional[str] = None
    user_id: str = "default"
    top_k_text: int = 10
    top_k_image: int = 5

@app.get("/")
async def root():
    return FileResponse("project_ui/index.html")

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
        image_paths = context.get("image_paths", [])
        router = AIRouter(llm_client)
        if image_paths:
            result = router.generate_response(request.question, context, image_paths)
            answer = result["answer"]
            image_desc = result["image_desc"]
            used_vision = result["used_vision"]
            tokens = result.get("tokens", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
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
        image_paths = context.get("image_paths", [])
        sources = context.get("text_results", [{}]) if "text_results" in context else []

        # Chat initialization logic
        if request.chat_id is None:
            request.chat_id = chat_store.create_chat(
                request.file_name or "New Chat", 
                request.message, 
                request.session_id, 
                request.user_id
            )
        else:
            chat_store.append_message(request.chat_id, "user", request.message, [], [])

        chat = chat_store.get_chat(request.chat_id)        
        if not chat:        
            request.chat_id = chat_store.create_chat(
                request.file_name or "Fallback Chat",               
                request.message,       
                request.session_id,           
                request.user_id
            )  
            chat = chat_store.get_chat(request.chat_id)
            
        chat_msgs = chat.messages if chat else []

        router = AIRouter(llm_client)
        if image_paths:
            result = router.generate_response(request.message, context, image_paths)
            image_desc = result.get("image_desc", "")
            text_context += f"\n\n[Vision Model Image Analysis]: {image_desc}"
            used_vision = True
        else:
            used_vision = False

        def normalize_img_url(raw: str) -> str:
            """Convert any stored image path → clean browser URL like /data/extracted_images/foo.png"""
            # Strip caption suffix (e.g. 'data/extracted_images/x.png | Figure from page 1')
            path = raw.split(" | ")[0].strip()
            # Normalize backslashes to forward slashes
            path = path.replace("\\", "/")
            # Remove any leading slash duplicates
            path = path.lstrip("/")
            # Ensure it starts with /
            return "/" + path

        # Determine if the user is asking about images/visuals/diagrams
        show_images = is_image_query(request.message)

        # Only build the images list when the query is image-related
        if show_images:
            images_list = [{"path": normalize_img_url(p), "caption": p.split(" | ")[1].strip() if " | " in p else "Document image"} for p in image_paths]
            images_list_str = [f"![{im['caption']}]({im['path']})" for im in images_list]
            image_instruction = f"Available images from the document (include them in your answer): {', '.join(images_list_str)}"
            image_rule = "6. The user has asked to see images/diagrams. Include ALL available images using their exact markdown syntax, e.g.: ![caption](url)."
        else:
            images_list = []  # No images returned for text-only queries
            image_instruction = ""  # No image section in prompt
            image_rule = "6. Do NOT include any images or image markdown in your answer. Answer in text only."

        # Determine if we have document context for this session
        has_context = bool(text_context and text_context.strip())

        system_prompt = f"""You are an intelligent, helpful AI assistant that ONLY answers questions based on the user's uploaded documents.

Context from the user's uploaded documents:
{text_context if has_context else '[NO DOCUMENT CONTEXT AVAILABLE]'}

{image_instruction}

STRICT RULES - YOU MUST FOLLOW THESE WITHOUT EXCEPTION:
1. You MUST answer ONLY from the Context provided above. Do NOT use your general training knowledge to answer any document-related questions.
2. If the Context is empty or marked as '[NO DOCUMENT CONTEXT AVAILABLE]', you MUST respond: "No document has been uploaded yet. Please upload a PDF or DOCX document first so I can answer your questions."
3. If the user's question cannot be answered from the Context above, respond: "I cannot find the answer to this in the uploaded document. Please check if the relevant document has been uploaded."
4. Do NOT hallucinate, guess, or infer facts that are not explicitly in the Context.
5. You may respond to simple greetings (e.g., "hi", "hello") briefly, but still remind the user to upload a document if no context is available.
{image_rule}
7. Do NOT output Python dictionaries or raw data structures.
"""
        messages = [{"role": "system", "content": system_prompt}]
        for m in chat_msgs:
            messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": request.message})

        response = llm_client.chat.completions.create(
            model="meta-llama/llama-3.1-8b-instruct",
            messages=messages,
            temperature=0.1
        )
        answer = response.choices[0].message.content

        # Store assistant response (sources/images)
        source_paths = [s.get('document', '') for s in sources if 'document' in s]
        
        # We should also only store clean paths in the chat history
        clean_image_paths = [im["path"] for im in images_list]
        chat_store.append_message(request.chat_id, "assistant", answer, source_paths, clean_image_paths)

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


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
