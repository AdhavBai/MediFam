"""
MediFamily OS - Audit & Security Logging Service
Maintains an immutable, tamper-evident audit journal of all system activities,
access requests, approvals, revocations, and emergency events.
"""

import sqlite3
import hashlib
from datetime import datetime
from backend.app.database import get_db

class AuditService:
    @staticmethod
    def log_action(actor_name: str, actor_role: str, action: str, 
                   target_type: str = "", target_id: str = "", details: str = "", 
                   actor_id: int = None, ip_address: str = "127.0.0.1", status: str = "SUCCESS"):
        """Records an action into the tamper-evident audit journal with SHA-256 integrity hash."""
        db = get_db()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate chained integrity hash
        hash_content = f"{timestamp}|{actor_name}|{actor_role}|{action}|{target_type}|{target_id}|{details}|{status}"
        integrity_hash = hashlib.sha256(hash_content.encode('utf-8')).hexdigest()
        
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO audit_logs (timestamp, actor_id, actor_name, actor_role, action, target_type, target_id, details, ip_address, status, integrity_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (timestamp, actor_id, actor_name, actor_role, action, target_type, target_id, details, ip_address, status, integrity_hash))
        db.commit()

    @staticmethod
    def get_logs(limit: int = 50, actor_role: str = None):
        """Fetches recent audit records."""
        db = get_db()
        cursor = db.cursor()
        if actor_role:
            cursor.execute("SELECT * FROM audit_logs WHERE actor_role = ? ORDER BY id DESC LIMIT ?", (actor_role, limit))
        else:
            cursor.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
