import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_query():
    # 1. Start a new session / upload file logic or use existing session_id
    # From inspect_db results, we have a session ID
    session_id = "e2da7776-006b-4007-aef1-1de9759b883a" # Replace with real one
    
    print(f"Testing RAG with session: {session_id}")
    
    payload = {
        "message": "what is in this document",
        "session_id": session_id,
        "chat_id": None,
        "file_name": "test_doc"
    }
    
    start = time.time()
    res = requests.post(f"{BASE_URL}/chat", json=payload)
    end = time.time()
    
    print(f"Status: {res.status_code}")
    print(f"Time: {end - start:.2f}s")
    
    if res.ok:
        data = res.json()
        print("\nRESPONSE:")
        print(data.get("response"))
        print("\nSOURCES:")
        print(data.get("sources"))
    else:
        print(res.text)

if __name__ == "__main__":
    test_query()
