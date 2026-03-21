import json
import os
import uuid
import time
from typing import List, Dict, Any, Optional

JSON_PATH = "data/chat_history.json"

def init_json():
    if not os.path.exists(JSON_PATH):
        os.makedirs(os.path.dirname(JSON_PATH), exist_ok=True)
        with open(JSON_PATH, 'w') as f:
            json.dump([], f)
    else:
        try:
            with open(JSON_PATH, 'r') as f:
                data = json.load(f)
                if not isinstance(data, list):
                    raise ValueError("Invalid JSON structure")
        except:
            with open(JSON_PATH, 'w') as f:
                json.dump([], f)

def load_data() -> List[Dict[str, Any]]:
    init_json()
    with open(JSON_PATH, 'r') as f:
        return json.load(f)

def save_data(data: List[Dict[str, Any]]):
    with open(JSON_PATH, 'w') as f:
        json.dump(data, indent=2)

def get_chats() -> List[Dict[str, Any]]:
    data = load_data()
    chats = []
    for c in data:
        chats.append({
            "chat_id": c["chat_id"],
            "title": c["title"],
            "timestamp": c["timestamp"],
            "message_count": len(c["messages"])
        })
    chats.sort(key=lambda x: x["timestamp"], reverse=True)
    return chats

def get_chat(chat_id: str) -> Optional[Dict[str, Any]]:
    data = load_data()
    for c in data:
        if c["chat_id"] == chat_id:
            return c
    return None

def create_chat(title: str = "New Chat") -> str:
    data = load_data()
    chat_id = str(uuid.uuid4())
    chat = {
        "chat_id": chat_id,
        "title": title,
        "messages": [],
        "timestamp": time.time()
    }
    data.append(chat)
    save_data(data)
    return chat_id

def append_message(chat_id: str, role: str, content: str, sources: List[str] = None, images: List[str] = None) -> bool:
    data = load_data()
    for chat in data:
        if chat["chat_id"] == chat_id:
            chat["messages"].append({
                "role": role,
                "content": content,
                "sources": sources or [],
                "images": images or []
            })
            save_data(data)
            return True
    return False

def delete_chat(chat_id: str) -> bool:
    data = load_data()
    original_len = len(data)
    data[:] = [c for c in data if c["chat_id"] != chat_id]
    save_data(data)
    return len(data) < original_len
