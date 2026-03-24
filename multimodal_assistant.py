import os
import time
import uvicorn
import base64
import io
from PIL import Image
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional
from contextlib import asynccontextmanager
from openai import OpenAI
import traceback

# Globals
llm_client = None
OPENROUTER_API_KEY = \"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\"  # From app_fixed_startup.py
BASE_URL = \"https://openrouter.ai/api/v1\"

print(\"🚀 Multimodal Assistant Starting...\")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global llm_client
    try:
        llm_client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=BASE_URL)
        print(\"✅ Vision LLM client ready (Llama 3.2-11B-Vision)\")
    except Exception as e:
        print(f\"❌ LLM init failed: {e}\")
    yield

app = FastAPI(title=\"Multimodal AI Assistant\", version=\"1.0\", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[\"*\"],
    allow_credentials=True,
    allow_methods=[\"*\"],
    allow_headers=[\"*\"],
)

app.mount(\"/static\", StaticFiles(directory=\"project_ui\"), name=\"static\")

class AnalyzeRequest(BaseModel):
    question: str
    image_b64: Optional[str] = None

def analyze_image_with_vision(question: str, image_pil: Image.Image) -> tuple[str, str]:
    \"\"\"Use Llama 3.2 Vision to describe image + answer question.\"\"\"
    try:
        # Encode PIL to base64
        buffered = io.BytesIO()
        image_pil.save(buffered, format='JPEG')
        img_b64 = base64.b64encode(buffered.getvalue()).decode()

        response = llm_client.chat.completions.create(
            model=\"meta-llama/llama-3.2-11b-vision-instruct\",
            messages=[
                {
                    \"role\": \"user\",
                    \"content\": [
                        {
                            \"type\": \"text\",
                            \"text\": f\"Analyze this image in detail (objects, people, text, diagrams). Then answer: {question}. Be accurate and specific. Describe what you see first, then answer.\"
                        },
                        {
                            \"type\": \"image_url\",
                            \"image_url\": {\"url\": f\"data:image/jpeg;base64,{img_b64}\"}
                        }
                    ]
                }
            ],
            temperature=0.1,
            max_tokens=1500
        )
        full_response = response.choices[0].message.content
        # Split description (first part) and answer
        description, _, answer = full_response.partition(\"\\nAnswer:\")
        return description.strip() or \"Detailed image analysis.\", answer.strip() or full_response
    except Exception as e:
        return f\"Vision analysis error: {str(e)}\", \"Unable to analyze image.\"

@app.get(\"/\", response_class=HTMLResponse)
async def root():
    with open(\"project_ui/multimodal.html\") as f:
        return HTMLResponse(content=f.read())

@app.get(\"/health\")
async def health():
    return {\"status\": \"ok\", \"vision_model\": \"llama-3.2-11b-vision-instruct\"}

@app.post(\"/analyze\")
async def analyze(request: AnalyzeRequest):
    print(f\"🖼️ Analyze: question='{request.question[:50]}...', has_image={request.image_b64 is not None}\")
    
    if not request.image_b64:
        return {\"answer\": \"No image was received. Please upload a valid image.\", \"used_vision\": False}
    
    try:
        # Decode base64
        header, image_b64 = request.image_b64.split(\",\", 1)
        if not image_b64:
            raise ValueError(\"Invalid base64\")
        
        image_data = base64.b64decode(image_b64)
        image = Image.open(io.BytesIO(image_data)).convert(\"RGB\")
        print(f\"✅ Image loaded: {image.size}, format={image.format}\")
        
        # Vision LLM
        description, answer = analyze_image_with_vision(request.question, image)
        
        return {
            \"answer\": answer,
            \"image_description\": description,
            \"used_vision\": True,
            \"image_size\": image.size
        }
    except Exception as e:
        print(f\"❌ Analyze error: {str(e)}\")
        traceback.print_exc()
        raise HTTPException(500, f\"Analysis failed: {str(e)}\")

@app.post(\"/analyze-file\")
async def analyze_file(file: UploadFile = File(...), question: str = Form(...)):
    \"\"\"Alternative: Multipart upload.\"\"\"
    if not file:
        raise HTTPException(400, \"No file\")
    
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert(\"RGB\")
        description, answer = analyze_image_with_vision(question, image)
        return {
            \"answer\": answer,
            \"image_description\": description,
            \"used_vision\": True,
            \"filename\": file.filename
        }
    except Exception as e:
        raise HTTPException(500, str(e))

if __name__ == \"__main__\":
    print(\"💡 Run: uvicorn multimodal_assistant:app --host 0.0.0.0 --port 8001 --reload\")
    uvicorn.run(\"multimodal_assistant:app\", host=\"0.0.0.0\", port=8001, reload=True)

