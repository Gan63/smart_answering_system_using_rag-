import os
import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from werkzeug.utils import secure_filename

from openai import OpenAI

# Initialize the OpenAI client
llm_client = OpenAI(
    api_key="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",
    base_url="https://openrouter.ai/api/v1"
)

import base64
import os
import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from werkzeug.utils import secure_filename

from openai import OpenAI

# Initialize the OpenAI client
llm_client = OpenAI(
    api_key="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",
    base_url="https://openrouter.ai/api/v1"
)

def ask_llm(text_context, image_context, question):
    if image_context:
        # We have an image, so we need to construct a multimodal prompt
        
        # Read the image file and encode it in base64
        with open(image_context, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
        
        # Construct the prompt with text and image
        prompt = [
            {
                "type": "text",
                "text": f"""
Use the following context to answer the question. 
If the question is about an image, use the provided image to answer it.

Text Context:
{text_context}

Question:
{question}
"""
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{encoded_image}"
                }
            }
        ]
        
        # Call a vision-capable model
        response = llm_client.chat.completions.create(
            model="google/gemini-pro-vision",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

    else:
        # No image, so we can use a standard text-based model
        prompt = f"""
Use the following context to answer the question.

Context:
{text_context}

Question:
{question}
"""
        response = llm_client.chat.completions.create(
            model="meta-llama/llama-3-8b-instruct",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

app = FastAPI()

# Add CORS middleware (only needed if frontend runs on a different origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
app.mount("/static", StaticFiles(directory="project_ui"), name="static")

# Configuration
UPLOAD_FOLDER = 'data'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

class AskRequest(BaseModel):
    question: str

@app.get("/")
async def root():
    return FileResponse('project_ui/index.html')

@app.get("/login")
async def login():
    return FileResponse('project_ui/login.html')

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/upload_pdf")
async def upload_pdf(file: UploadFile = File(...)):
    from ingestion.ingest_pdf import ingest_pdf

    if not file:
        raise HTTPException(status_code=400, detail="No file part")
    try:
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        
        ingest_pdf(file_path)
        return {"message": f"File {filename} uploaded and ingested successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest file: {str(e)}")

@app.post("/ask")
async def ask(request: AskRequest):
    from agent.planner import agent_query

    question = request.question
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
    try:
        context = agent_query(question)
        text_context = context.get("text_context", "")
        image_context = context.get("image_context")

        answer = ask_llm(text_context, image_context, question)
        
        # The context to return to the UI can be a simplified string version
        display_context = text_context
        if image_context:
            display_context += f"\n[Image Context: {os.path.basename(image_context)}]"
            
        return {"answer": answer, "context": display_context}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get answer: {str(e)}")

if __name__ == "__main__":
    print("Run the server with: uvicorn app:app --host 127.0.0.1 --port 8000")
    print("This will serve both the backend API and the frontend.")
