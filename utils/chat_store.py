import json
import os
import uuid
import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

# Models
class Message(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    sources: Optional[List[str]] = None
    images: Optional[List[str]] = None

class Chat(BaseModel):
    chat_id: str
    title: str
    messages: List[Dict[str, Any]]  # JSON serializable
    timestamp: float
    user_id: str = "default"

JSON_PATH = "data/chat_history.json"

def init_json():
    """Ensure JSON file exists with empty list."""
    if not os.path.exists(JSON_PATH):
        os.makedirs(os.path.dirname(JSON_PATH), exist_ok=True)
        with open(JSON_PATH, 'w') as f:
            json.dump([], f)
    else:
        # Validate structure
        try:
            with open(JSON_PATH, 'r') as f:
                data = json.load(f)
                if not isinstance(data, list):
                    raise ValueError("Invalid JSON structure")
        except:
            # Reset if corrupted
            with open(JSON_PATH, 'w') as f:
                json.dump([], f)

def load_data() -> List[Dict[str, Any]]:
    init_json()
    with open(JSON_PATH, 'r') as f:
        return json.load(f)

def save_data(data: List[Dict[str, Any]]):
    with open(JSON_PATH, 'w') as f:
        json.dump(data, f, indent=2)

class ChatStore:
    def create_chat(self, file_name: str, first_message: str, session_id: str, user_id: str = "default") -> str:
        """Create new chat, title from file_name."""
        init_json()
        chat_id = str(uuid.uuid4())
        # Title: file basename without extension
        title = os.path.splitext(os.path.basename(file_name))[0] if file_name else "Untitled"
        timestamp = time.time()
        messages = [{"role": "user", "content": first_message, "sources": [], "images": []}]
        chat_data = {
            "chat_id": chat_id,
            "title": title,
            "messages": messages,
            "timestamp": timestamp,
            "user_id": user_id
        }
        data = load_data()
        data.append(chat_data)
        save_data(data)
        print(f"Saving chat: {chat_id}, title: {title}, Total chats: {len(data)}")
        return chat_id

    def get_chats(self, user_id: str = "default") -> List[Chat]:
        """List user's chats (recent first)."""
        init_json()
        data = load_data()
        chats = []
        for chat_dict in data:
            if chat_dict.get("user_id") == user_id:
                chats.append(Chat(**chat_dict))
        chats.sort(key=lambda c: c.timestamp, reverse=True)
        print(f"Fetched {len(chats)} chats for user {user_id}")
        return chats

    def get_chat(self, chat_id: str) -> Optional[Chat]:
        """Get full chat by ID."""
        init_json()
        data = load_data()
        for chat_dict in data:
            if chat_dict.get("chat_id") == chat_id:
                return Chat(**chat_dict)
        return None

    def append_message(self, chat_id: str, role: str, content: str, sources: List[str] = None, images: List[str] = None) -> bool:
        """Append message to chat."""
        init_json()
        data = load_data()
        for chat_dict in data:
            if chat_dict.get("chat_id") == chat_id:
                new_msg = {
                    "role": role,
                    "content": content,
                    "sources": sources or [],
                    "images": images or []
                }
                chat_dict["messages"].append(new_msg)
                save_data(data)
                print(f"Appended {role} message to chat {chat_id}, Total chats: {len(data)}")
                return True
        return False

    def delete_chat(self, chat_id: str) -> bool:
        """Delete a chat by ID."""
        init_json()
        data = load_data()
        original_len = len(data)
        data[:] = [c for c in data if c.get("chat_id") != chat_id]
        save_data(data)
        deleted = len(data) < original_len
        if deleted:
            print(f"Deleted chat {chat_id}, Total chats: {len(data)}")
        return deleted

# Global instance
chat_store = ChatStore()

