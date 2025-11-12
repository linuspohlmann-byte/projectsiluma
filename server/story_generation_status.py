"""
Story Generation Status Tracking
Tracks the progress of story generation for real-time updates
"""

import threading
from datetime import datetime, UTC
from typing import Dict, Optional

# In-memory storage for generation status
# Format: {group_id: {status: str, step: str, progress: float, message: str, error: Optional[str]}}
_generation_status: Dict[int, Dict] = {}
_status_lock = threading.Lock()

def set_generation_status(group_id: int, status: str, step: str = '', progress: float = 0.0, message: str = '', error: Optional[str] = None):
    """Set the generation status for a group"""
    with _status_lock:
        _generation_status[group_id] = {
            'status': status,  # 'generating', 'completed', 'failed'
            'step': step,  # Current step name
            'progress': progress,  # 0.0 to 1.0
            'message': message,  # Human-readable message
            'error': error,  # Error message if failed
            'updated_at': datetime.now(UTC).isoformat()
        }

def get_generation_status(group_id: int) -> Optional[Dict]:
    """Get the generation status for a group"""
    with _status_lock:
        return _generation_status.get(group_id)

def clear_generation_status(group_id: int):
    """Clear the generation status for a group (after completion)"""
    with _status_lock:
        if group_id in _generation_status:
            del _generation_status[group_id]

def cleanup_old_statuses(max_age_seconds: int = 3600):
    """Clean up old status entries (older than max_age_seconds)"""
    with _status_lock:
        now = datetime.now(UTC)
        to_remove = []
        for group_id, status_data in _generation_status.items():
            updated_at_str = status_data.get('updated_at', '')
            if updated_at_str:
                try:
                    updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
                    age_seconds = (now - updated_at.replace(tzinfo=None)).total_seconds()
                    if age_seconds > max_age_seconds:
                        to_remove.append(group_id)
                except Exception:
                    pass
        
        for group_id in to_remove:
            del _generation_status[group_id]

