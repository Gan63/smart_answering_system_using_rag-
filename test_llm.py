from openai import OpenAI
import os

api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    print("❌ ERROR: OPENROUTER_API_KEY not set.")
    print("1. Get free key: https://openrouter.ai/keys")
    print("2. Windows: set OPENROUTER_API_KEY=")
    print("3. See .env.example")
    exit(1)

client = OpenAI(
    api_key="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",
    base_url="https://openrouter.ai/api/v1"
)

print("✅ LLM Test Ready (OpenRouter). Type messages (exit to stop).")

while True:
    user_input = input("\nYou: ")
    if user_input.lower() == "exit":
        break

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-3.2-8b-instruct",
            messages=[{"role": "user", "content": user_input}]
        )
        print("LLM:", response.choices[0].message.content)
    except Exception as e:
        print(f"❌ LLM Error: {e}")
