"""
MediFamily OS - Notification Service & Real-Time Event Bus
Dispatches in-app notifications and broadcasts real-time SSE / WebSocket events to clients.
"""

import json
import queue
import threading
from datetime import datetime
from backend.app.database import get_db

class NotificationService:
    # Event listeners mapping: user_id -> list of queues
    _listeners = {}
    _lock = threading.Lock()

    @classmethod
    def subscribe(cls, user_id: int) -> queue.Queue:
        """Register a client queue for real-time live events."""
        with cls._lock:
            q = queue.Queue(maxsize=100)
            if user_id not in cls._listeners:
                cls._listeners[user_id] = []
            cls._listeners[user_id].append(q)
            return q

    @classmethod
    def unsubscribe(cls, user_id: int, q: queue.Queue):
        """Unregister a client queue."""
        with cls._lock:
            if user_id in cls._listeners:
                if q in cls._listeners[user_id]:
                    cls._listeners[user_id].remove(q)
                if not cls._listeners[user_id]:
                    del cls._listeners[user_id]

    @classmethod
    def broadcast_to_user(cls, user_id: int, event_type: str, data: dict):
        """Pushes a real-time event to all active sessions of a specific user."""
        event_payload = {
            "event": event_type,
            "data": data,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with cls._lock:
            if user_id in cls._listeners:
                for q in cls._listeners[user_id]:
                    try:
                        q.put_nowait(event_payload)
                    except queue.Full:
                        pass

    @classmethod
    def broadcast_to_all(cls, event_type: str, data: dict):
        """Pushes a real-time event to all connected users across the system."""
        event_payload = {
            "event": event_type,
            "data": data,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with cls._lock:
            for user_id, q_list in cls._listeners.items():
                for q in q_list:
                    try:
                        q.put_nowait(event_payload)
                    except queue.Full:
                        pass

    @classmethod
    def send_notification(cls, user_id: int, notification_type: str, title: str, message: str, data: dict = None) -> int:
        """Saves notification in database and immediately broadcasts via real-time event bus."""
        db = get_db()
        data_str = json.dumps(data or {})
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO notifications (user_id, type, title, message, data_json, is_read)
            VALUES (?, ?, ?, ?, ?, 0)
        """, (user_id, notification_type, title, message, data_str))
        notif_id = cursor.lastrowid
        db.commit()

        # Push to real-time stream
        cls.broadcast_to_user(user_id, "notification", {
            "id": notif_id,
            "type": notification_type,
            "title": title,
            "message": message,
            "data": data or {},
            "created_at": datetime.now().strftime("%H:%M:%S")
        })

        return notif_id

    @staticmethod
    def get_user_notifications(user_id: int, limit: int = 20):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT * FROM notifications 
            WHERE user_id = ? 
            ORDER BY id DESC LIMIT ?
        """, (user_id, limit))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["data"] = json.loads(d.get("data_json") or "{}")
            except Exception:
                d["data"] = {}
            result.append(d)
        return result

    @staticmethod
    def mark_as_read(notification_id: int, user_id: int):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            UPDATE notifications 
            SET is_read = 1 
            WHERE id = ? AND user_id = ?
        """, (notification_id, user_id))
        db.commit()
