import os
from openai import OpenAI
from agent.planner import agent_query
from database.chroma_client import get_text_collection
from ingestion.ingest_pdf import ingest_pdf
from ingestion.ingest_image import ingest_image
from db import init_db

# ✅ Load API key safely
api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    raise ValueError("❌ OPENROUTER_API_KEY not set")

llm_client = OpenAI(
    api_key=api_key,
    base_url="https://openrouter.ai/api/v1"
)

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


if __name__ == "__main__":
    print("🚀 Multimodal RAG CLI")

    # ✅ Initialize DB (important)
    init_db()

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

    while True:
        query = input("\nAsk (exit): ")
        if query.lower() == "exit":
            break

        context = agent_query(query)
        answer = ask_llm(context, query)
        print("Answer:", answer)
