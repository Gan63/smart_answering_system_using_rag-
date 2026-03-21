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
            model="meta-llama/llama-3.2-11b-vision-instruct",
            messages=[{"role": "user", "content": user_input}]
        )
        print("LLM:", response.choices[0].message.content)
    except Exception as e:
        print(f"❌ LLM Error: {e}")
