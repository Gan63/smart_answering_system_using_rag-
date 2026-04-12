import os
from openai import OpenAI

client = OpenAI(
    api_key="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",
    base_url="https://openrouter.ai/api/v1"
)

models = ["google/gemini-2.0-flash-001", "meta-llama/llama-3.1-8b-instruct", "google/gemini-pro-1.5"]

for model in models:
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5
        )
        print(f"Success {model}:", response.choices[0].message.content)
        break
    except Exception as e:
        print(f"Error {model}:", e)
