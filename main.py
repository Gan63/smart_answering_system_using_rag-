import os
from openai import OpenAI
from agent.planner import agent_query
from database.chroma_client import get_text_collection
from ingestion.ingest_pdf import ingest_pdf
from ingestion.ingest_image import ingest_image

# LLM Setup
api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    print("❌ ERROR: OPENROUTER_API_KEY not set.")
    print("1. Get free key: https://openrouter.ai/keys")
    print("2. set OPENROUTER_API_KEY")
    print("3. See .env.example")
    exit(1)

llm_client = OpenAI(
    api_key="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",
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

    # Check if vectors already exist
    collection = get_text_collection()
    if collection.count() == 0:
        print("📥 Ingesting data...")
        ingest_pdf("data/Microsoft-Policymaker-Guide-Privacy.pdf")
        ingest_pdf("data/SMB_University_120307_Networking_Fundamentals.pdf")
        try:
            from ingestion.ingest_docx import ingest_docx
            ingest_docx("data/sample.docx")
        except ImportError:
            print("⚠️ python-docx not installed, skipping DOCX (pip install python-docx)")
        except FileNotFoundError:
            print("⚠️ No sample.docx, skipping")
        ingest_image("data/Screenshot.png")  # Adjust if file exists
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
