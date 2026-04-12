import os
from openai import OpenAI
import json

OPENROUTER_API_KEY = "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"
BASE_URL = "https://openrouter.ai/api/v1"

client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url=BASE_URL
)

def list_flux():
    import requests
    response = requests.get(
        url="https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
    )
    if response.status_code == 200:
        models = response.json().get("data", [])
        flux_models = [m["id"] for m in models if "flux" in m["id"]]
        if flux_models:
            print("Available Flux Models:")
            for m in flux_models:
                print(f" - {m}")
        else:
            print("No Flux models found for this key.")
    else:
        print(f"Failed to fetch models: {response.status_code} - {response.text}")

if __name__ == "__main__":
    list_flux()
