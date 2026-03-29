from typing import Optional, Dict, Any, List
from session_store import session_store
from utils.chat_history import ChatMessage

def add_to_history(session_id: str, query: str, answer: str, context: Dict[str, Any], 
                   images: List[Dict[str, Any]], tokens: Dict[str, int]):
    '''
    Add message to session history.
    '''
    session_store.add_message(session_id, query, answer, context, images, tokens)

def get_chat_history(session_id: str) -> Optional[List[ChatMessage]]:
    '''
    Get formatted chat history for session.
    '''
    history = session_store.get_history(session_id)
    if history:
        return history
    return None

def get_session_stats(session_id: str) -> Optional[Dict[str, Any]]:
    '''
    Get session message_count, total_tokens.
    '''
    session = session_store.get_session(session_id)
    if session:
     return {
            'message_count': getattr(session, 'message_count', 0),
            'total_tokens': getattr(session, 'total_tokens', 0),
            'chunk_count': getattr(session, 'chunk_count', 0),
            'vector_count': getattr(session, 'vector_count', 0)
        }
    return None
