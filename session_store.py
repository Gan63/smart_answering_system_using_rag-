import time
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from utils.chat_history import ChatMessage, serialize_history
from database.chroma_client import get_session_stats

class Message(BaseModel):
    role: str
    content: str

class SessionInfo(BaseModel):
    filename: str
    created_at: float
    session_id: str
    user_id: str = "default"
    chat_history: List[Dict[str, Any]] = []
    message_count: int = 0
    total_tokens: int = 0
    title: str = "New Chat"
    last_updated: float = 0
    chunk_count: int = 0
    vector_count: int = 0

class SessionStore:
    def __init__(self):
        self.sessions: Dict[str, SessionInfo] = {}
        self.chat_history: Dict[str, list[Message]] = {}

    def create_session(self, filename: str, session_id: str, user_id: str = "default") -> str:
        print(f"[DEBUG] SessionStore.create_session called with filename='{filename}', session_id='{session_id}', user_id='{user_id}'")
        self.sessions[session_id] = SessionInfo(
            filename=filename,
            created_at=time.time(),
            session_id=session_id,
            user_id=user_id,
            title=filename[:30] + "..." if len(filename) > 30 else filename
        )
        self.chat_history[session_id] = []
        return session_id

    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        return self.sessions.get(session_id)

    def get_all_sessions(self, user_id: str = "default") -> list[SessionInfo]:
        return [s for s in self.sessions.values() if s.user_id == user_id]

    def get_sessions(self, user_id: str = "default") -> list[dict]:
        return [
            {
                "id": info.session_id,
                "title": info.title,
                "created": info.created_at,
                "last_updated": info.last_updated,
                "filename": info.filename
            }
            for info in self.sessions.values() if info.user_id == user_id
        ]

    def increment_message_count(self, session_id: str) -> bool:
        session = self.get_session(session_id)
        if session:
            session.message_count += 1
            return True
        return False

    def add_tokens(self, session_id: str, tokens: Dict[str, int]) -> bool:
        session = self.get_session(session_id)
        if session and 'total_tokens' in tokens:
            session.total_tokens += tokens['total_tokens']
            return True
        return False

    def add_message(self, session_id: str, query: str, answer: str, 
                   context: Dict[str, Any], images: List[Dict[str, Any]], 
                   tokens: Dict[str, int]) -> bool:
        session = self.get_session(session_id)
        if session:
            timestamp = time.time()
            message = {
                'query': query,
                'answer': answer,
                'context': context,
                'images': images,
                'timestamp': timestamp,
                'tokens': tokens
            }
            session.chat_history.append(message)
            self.increment_message_count(session_id)
            self.add_tokens(session_id, tokens)
            session.last_updated = timestamp
            return True
        return False

    def get_history(self, session_id: str) -> Optional[List[ChatMessage]]:
        session = self.get_session(session_id)
        if session and session.chat_history:
            return serialize_history(session.chat_history)
        return None

    def update_stats(self, session_id: str):
        "Update chunk_count and vector_count from Chroma stats."
        session = self.get_session(session_id)
        if not session:
            return
        chroma_stats = get_session_stats(session_id)
        if chroma_stats:
            session.chunk_count = chroma_stats.get('text_count', 0)
            session.vector_count = chroma_stats.get('text_count', 0) + chroma_stats.get('image_count', 0)

    def delete_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            del self.sessions[session_id]
        if session_id in self.chat_history:
            del self.chat_history[session_id]
        return True

session_store = SessionStore()
