import os
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI

from agent.planner import agent_query
from database.chroma_client import get_text_collection
from ingestion.ingest_pdf import ingest_pdf
from ingestion.ingest_image import ingest_image
from db import init_db, create_tables

# ✅ Init FastAPI
app = FastAPI()

# ✅ Load API key
api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    raise ValueError("❌ OPENROUTER_API_KEY not set")

llm_client = OpenAI(
    api_key=api_key,
    base_url="https://openrouter.ai/api/v1"
)

# ✅ Request schema
class QueryRequest(BaseModel):
    question: str


# ✅ LLM function
def ask_llm(context, question):
    prompt = f"""Use the following context to answer the question.

Context:
{context}

Question:
{question}"""

    response = llm_client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content


# ✅ Startup event
@app.on_event("startup")
def startup():
    print("🚀 Starting RAG API...")

    # DB init
    init_db()
    create_tables()

    # Ingestion check
    collection = get_text_collection()

    if collection.count() == 0:
        print("📥 Ingesting data...")
        ingest_pdf("data/Microsoft-Policymaker-Guide-Privacy.pdf")
        ingest_pdf("data/SMB_University_120307_Networking_Fundamentals.pdf")

        try:
            from ingestion.ingest_docx import ingest_docx
            ingest_docx("data/sample.docx")
        except:
            print("⚠️ DOCX skipped")

        ingest_image("data/Screenshot.png")
        print("✅ Ingestion complete")
    else:
        print("✅ Using existing vectors")


# ✅ Health check
@app.get("/")
def home():
    return {"message": "Smart RAG API running 🚀"}


# ✅ Main RAG endpoint
@app.post("/ask")
def ask_question(req: QueryRequest):
    context = agent_query(req.question)
    answer = ask_llm(context, req.question)
    return {"answer": answer}
