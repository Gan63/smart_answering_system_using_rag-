from openai import OpenAI

client = OpenAI(
    api_key="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",
    base_url="https://openrouter.ai/api/v1"
)

while True:

    user_input = input("You: ")

    if user_input.lower() == "exit":
        break

    response = client.chat.completions.create(
        model="meta-llama/llama-3-8b-instruct",
        messages=[
            {"role": "user", "content": user_input}
        ]
    )

    print("LLM:", response.choices[0].message.content)
