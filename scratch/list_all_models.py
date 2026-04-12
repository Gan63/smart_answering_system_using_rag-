import os
import requests

OPENROUTER_API_KEY = "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"

def list_all():
    response = requests.get(
        url="https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
    )
    if response.status_code == 200:
        models = response.json().get("data", [])
        print(f"Total Models Available: {len(models)}")
        # Print first 20 to see what we have
        for m in models[:20]:
            print(f" - {m['id']}")
    else:
        print(f"Failed: {response.status_code}")

if __name__ == "__main__":
    list_all()
