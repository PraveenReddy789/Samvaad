from typing import List, Dict, Any, Optional
from backend.db.database import SessionLocal
from backend.db.models import CallDisposition, Customer


class CustomerMemoryManager:
    """Manages short-term conversation state and long-term call history memory."""

    def __init__(self):
        # In-memory session dialogues: session_id -> list of {"role": "user"|"assistant", "content": str}
        self.active_sessions: Dict[str, List[Dict[str, str]]] = {}

    def get_conversation_history(self, session_id: str, limit: int = 6) -> List[Dict[str, str]]:
        """Returns the recent turns for a session."""
        history = self.active_sessions.get(session_id, [])
        return history[-limit:]

    def add_message(self, session_id: str, role: str, content: str):
        """Appends a message to the active session history."""
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = []
        self.active_sessions[session_id].append({"role": role, "content": content})

    def get_customer_historical_context(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Fetches previous call logs and outcomes from the database."""
        db = SessionLocal()
        try:
            calls = (
                db.query(CallDisposition)
                .filter(CallDisposition.customer_id == customer_id.strip())
                .order_by(CallDisposition.timestamp.desc())
                .all()
            )
            if not calls:
                return None

            latest = calls[0]
            return {
                "total_past_calls": len(calls),
                "last_call_timestamp": latest.timestamp,
                "last_intent": latest.intent,
                "last_outcome": latest.outcome,
                "last_sentiment": latest.sentiment,
                "last_summary": latest.summary,
            }
        finally:
            db.close()


_memory_instance = None


def get_memory_manager() -> CustomerMemoryManager:
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = CustomerMemoryManager()
    return _memory_instance
