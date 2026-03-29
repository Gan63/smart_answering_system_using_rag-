import threading
from typing import Dict, Any, Optional
from datetime import datetime

# Thread-safe session status
_status_store: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()

def init_status(session_id: str, filename: str):
    """Initialize processing status"""
    with _lock:
        _status_store[session_id] = {
            'status': 'processing',
            'filename': filename,
            'start_time': datetime.now().isoformat(),
            'text_count': 0,
            'image_count': 0,
            'error': None
        }

def update_status(session_id: str, **kwargs):
    """Update status fields"""
    with _lock:
        if session_id in _status_store:
            _status_store[session_id].update(kwargs)

def set_complete(session_id: str, text_count: int, image_count: int):
    """Mark complete"""
    update_status(session_id, status='complete', text_count=text_count, image_count=image_count, end_time=datetime.now().isoformat())

def set_error(session_id: str, error: str):
    """Mark error"""
    update_status(session_id, status='error', error=str(error)[:200])

def get_status(session_id: str) -> Optional[Dict[str, Any]]:
    """Get status for session"""
    from session_store import session_store
    with _lock:
        status = _status_store.get(session_id)
        if status:
            session = session_store.get_session(session_id)
            if session:
                status['chunk_count'] = session.chunk_count
                status['vector_count'] = session.vector_count
        return status

def clear_status(session_id: str):
    """Cleanup old status"""
    with _lock:
        _status_store.pop(session_id, None)
