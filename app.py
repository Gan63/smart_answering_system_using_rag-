import base64
import os
import uvicorn
import traceback
import uuid
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from werkzeug.utils import secure_filename
from openai import OpenAI
from agent.planner import agent_query
from ingestion.ingest_pdf import ingest_pdf
from database.chroma_client import delete_session_data
from session_store import session_store
from contextlib import asynccontextmanager

# =========================
# Globals
# =========================
llm_client = None
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
UPLOAD_FOLDER = "data"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global llm_client
    if not OPENROUTER_API_KEY:
        raise ValueError("[X] Please set OPENROUTER_API_KEY")

    llm_client = OpenAI(
        api_key="enter your api_key",
        base_url="enter your url"
    )
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    pass  # Startup complete
    yield
    # Shutdown
    pass  # Shutdown

# =========================
# 🚀 FASTAPI SETUP
# =========================
app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="project_ui"), name="static")
app.mount("/data", StaticFiles(directory="data", html=False), name="data")

# =========================
# 🤖 LLM FUNCTION
# =========================
def ask_llm(text_context, image_context, question):
    try:
        messages = []
        if image_context and os.path.exists(image_context):
            with open(image_context, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
            
            messages.append({
                "type": "text",
                "text": f"Use the following context to answer the question.\n\nText Context:\n{text_context}\n\nQuestion:\n{question}"
            })
            messages.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encoded_image}"}
            })
            model = "openai/gpt-4o-mini"
        else:
            messages.append({
                "type": "text",
                "text": f"Use the following context to answer the question.\n\nContext:\n{text_context}\n\nQuestion:\n{question}"
            })
            model = "meta-llama/llama-3-8b-instruct"

        response = llm_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": messages}]
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

# =========================
# 🌐 ROUTES
# =========================
@app.get("/")
async def root():
    return FileResponse("project_ui/index.html")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/favicon.ico")
async def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    pass  # Upload hit
    pass  # Filename logged
    pass
    try:
        if not file:
            raise HTTPException(status_code=400, detail="No file uploaded")

        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
 
        session_id = str(uuid.uuid4())
        
        pass
        ingest_pdf(pdf_path=file_path, session_id=session_id)
        pass
        session_store.create_session(filename)
        
        pass
        return {
            "message": f"✅ {filename} uploaded successfully. Ask queries related to this document.",
            "session_id": session_id,
            "filename": filename
        }

    except Exception as e:
        print(f"[ERROR] Upload: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query")
async def query(request: AskRequest):
    print(f"DEBUG QUERY - session_id: '{request.session_id}' question: '{request.question[:50]}...'")
    if not request.session_id:
        return {"answer": "Please upload a document first.", "error": "No session"}

    try:
        context = agent_query(user_query=request.question, session_id=request.session_id)
        print(f"DEBUG context keys: {list(context.keys()) if context else None}")
        print(f"DEBUG text_context len: {len(context.get('text_context', '')) if context else 0}")
        print(f"DEBUG image_context: {context.get('image_context')}")
        
        if not context or not context.get('text_context'):
            return {"answer": "No relevant information found in the document. Try rephrasing.", "error": "No context", "context": context or {}}

        answer = ask_llm(
            text_context=context.get("text_context"),
            image_context=context.get("image_context"),
            question=request.question
        )
        return {
            "answer": answer,
            "context": context,
            "image_paths": context.get("image_paths", [])
        }
    except Exception as e:
        print(f"DEBUG FULL ERROR in query: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"answer": f"Server error: {str(e)}", "error": str(e), "context": {}}




@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    try:
        delete_session_data(session_id)
        return {"message": f"✅ Session {session_id} and its data have been deleted."}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to delete session {session_id}: {e}")

# =========================
# ▶️ RUN
# =========================
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
