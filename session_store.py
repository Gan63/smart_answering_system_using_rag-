import time
from typing import Dict, Optional
from pydantic import BaseModel

class SessionInfo(BaseModel):
    filename: str
    created_at: float
    session_id: str

class SessionStore:
    def __init__(self):
        self.sessions: Dict[str, SessionInfo] = {}

    def create_session(self, filename: str) -> str:
        session_id = str(time.time()) + str(hash(filename))
        self.sessions[session_id] = SessionInfo(
            filename=filename,
            created_at=time.time(),
            session_id=session_id
        )
        return session_id

    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        return self.sessions.get(session_id)

    def get_all_sessions(self) -> list[SessionInfo]:
        return list(self.sessions.values())

    def delete_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

session_store = SessionStore()
