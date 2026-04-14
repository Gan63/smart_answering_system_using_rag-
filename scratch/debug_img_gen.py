import os
import re
from openai import OpenAI

# Hardcoded test from app.py
OPENROUTER_API_KEY = "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"
BASE_URL = "https://openrouter.ai/api/v1"

client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url=BASE_URL
)

def test_gen():
    try:
        print("Testing Image Generation via Gemini 3 Pro...")
        prompt = "A futuristic glass laboratory with floating holographic AI interfaces, high quality, 8k"
        
        response = client.chat.completions.create(
            model="google/gemini-3-pro-image-preview",
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        )
        
        content = response.choices[0].message.content
        print(f"Raw Response Received: {content[:150]}...")
        
        # Extract URL using the same logic as our AIRouter
        url_match = re.search(r'\((https?://[^\)]+)\)', content)
        if url_match:
            img_url = url_match.group(1)
            print(f"SUCCESS! Image URL found: {img_url}")
            return True
        
        if "https://" in content:
            url_match = re.search(r'https?://[^\s\)]+', content)
            if url_match:
                print(f"SUCCESS! Image URL found: {url_match.group(0)}")
                return True

        print("FAILED: Could not extract image URL from response content.")
        return False
            
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    test_gen()
