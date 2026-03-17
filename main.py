from ingestion.ingest_pdf import ingest_pdf
from ingestion.ingest_image import ingest_image
from agent.planner import agent_query
from database.chroma_client import get_text_collection
from openai import OpenAI


llm_client = OpenAI(
    api_key="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",

    base_url="https://openrouter.ai/api/v1"
)


def ask_llm(context, question):

    prompt = f"""
Use the following context to answer the question.

Context:
{context}

Question:
{question}
"""

    response = llm_client.chat.completions.create(
        model="meta-llama/llama-3-8b-instruct",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content


if __name__ == "__main__":

    print("Multimodal Agentic RAG Started")

    # Check if vectors already exist
    collection = get_text_collection()

    if collection.count() == 0:
        print("No vectors found. Ingesting documents...")

        ingest_pdf("data/RESEARCH_PAPER.pdf")
        ingest_image("data/Screenshot.png")

        print("Documents ingested successfully!")

    else:
        print("Vector database already exists. Skipping ingestion.")

    while True:

        query = input("\nAsk something (type exit): ")

        if query.lower() == "exit":
            break

        context = agent_query(query)

        answer = ask_llm(context, query)

        print("\nAnswer:\n", answer)
        print("\nRetrieved Context:\n", context[:500])
