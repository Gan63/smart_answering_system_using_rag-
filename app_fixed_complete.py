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
from database.chroma_client import delete_session_data, get_session_stats
from session_store import session_store
from utils.token_counter import count_tokens_from_response
from utils.session_manager import add_to_history, get_chat_history
from utils.chat_store import chat_store
from ingestion_status import init_status, update_status, set_complete, set_error
from typing import Optional
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
    top_k_text: int = 10
    top_k_image: int = 1

@app.get("/")
async def root():
    return FileResponse("project_ui/index.html")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/query")
async def query_endpoint(request: AskRequest):
    try:
        context = agent_query(request.question, request.session_id, request.top_k_text, request.top_k_image)
        
        if not context or not context.get('text_context'):
            return {"answer": "No relevant information found in the document. Try rephrasing your question after ingestion completes.", "error": "No context", "images": [], "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}

        text_context = context.get("text_context", "")
        images_list = context.get("images", [])
        answer = ask_llm(text_context, images_list, request.question)
        
        return {"answer": answer, "context": context, "images": images_list, "tokens": {"total_tokens": 0}}
    except Exception as e:
        traceback.print_exc()
        return {"answer": f"Error: {str(e)}"}

@app.post("/upload")
async def upload(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    print(f"📤 Upload hit: {file.filename}")
    try:
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        
        session_id = str(uuid.uuid4())
        session_store.create_session(filename, session_id)
        init_status(session_id, filename)
        
        ext = os.path.splitext(filename)[1].lower()
        def ingest_file():
            try:
                update_status(session_id, step="ingesting")
                if ext == '.pdf':
                    ingest_pdf(file_path, session_id)
                elif ext == '.docx':
                    ingest_docx(file_path, session_id)
                elif ext in ['.png', '.jpg', '.jpeg', '.gif']:
                    ingest_image(file_path, session_id)
                else:
                    raise ValueError(f"Unsupported: {ext}")
                stats = get_session_stats(session_id)
                set_complete(session_id, stats['text_count'], stats['image_count'])
            except Exception as e:
                set_error(session_id, str(e))
        
        background_tasks.add_task(ingest_file)
        return {"session_id": session_id, "filename": filename, "status_url": f"/ingest_status/{session_id}", "message": "Uploaded. Processing..."}
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ingest_status/{session_id}")
async def get_ingest_status(session_id: str):
    from ingestion_status import get_status
    status = get_status(session_id)
    if status:
        status['chroma_stats'] = get_session_stats(session_id)
    return status or {"status": "not_found"}

@app.get("/history/{session_id}")
async def get_history(session_id: str):
    try:
        history = get_chat_history(session_id)
        stats = get_session_stats(session_id)
        return {"history": [msg.dict() for msg in history] if history else [], "stats": stats or {}}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions")
async def get_sessions():
    try:
        return {"sessions": [s.dict() for s in session_store.get_all_sessions()]}
    except:
        return {"sessions": []}

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        context = agent_query(request.message, request.session_id, request.top_k_text, request.top_k_image)
        text_context = context.get("text_context", "") if context else ""
        images_list = context.get("images", []) if context else []
        answer = ask_llm(text_context, images_list, request.message)
        return {"response": answer, "chat_id": request.chat_id or "new", "tokens": 0}
    except Exception as e:
        print(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    delete_session_data(session_id)
    return {"message": "Session deleted"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
