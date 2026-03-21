from typing import List, Dict, Any
from pydantic import BaseModel

class ChatMessage(BaseModel):
    query: str
    answer: str
    context: Dict[str, Any]
    images: List[Dict[str, Any]]
    timestamp: float
    tokens: Dict[str, int]

def serialize_history(history: List[Dict]) -> List[ChatMessage]:
    '''
    Convert raw dict history to typed ChatMessage list.
    '''
    return [ChatMessage(**msg) for msg in history]
