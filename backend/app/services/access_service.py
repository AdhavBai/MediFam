"""
MediFamily OS - Access Control & Temporary Resource Allocation Service
Implements the 7-step normal access workflow, active session timers,
and immediate real-time revocation via WebSockets / SSE.
"""

from datetime import datetime, timedelta
from backend.app.database import get_db
from backend.app.auth import generate_session_token
from backend.app.services.notification_service import NotificationService
from backend.app.services.audit_service import AuditService
from backend.app.os_engine import os_engine

class AccessService:
    @staticmethod
    def create_normal_request(doctor_user_id: int, health_id: str, reason: str, duration_minutes: int = 15):
        db = get_db()
        cursor = db.cursor()
        
        # 1. Fetch Doctor info
        cursor.execute("""
            SELECT d.id as doctor_id, d.doctor_name, d.hospital_id, h.name as hospital_name
            FROM doctors d
            JOIN hospitals h ON d.hospital_id = h.id
            WHERE d.user_id = ?
        """, (doctor_user_id,))
        doc = cursor.fetchone()
        if not doc:
            raise ValueError("Doctor profile not found for user")

        # 2. Fetch Patient info
        cursor.execute("SELECT id, user_id, relationship FROM patients WHERE UPPER(health_id) = UPPER(?)", (health_id.strip(),))
        pat = cursor.fetchone()
        if not pat:
            raise ValueError(f"Patient with Health ID '{health_id}' not found")

        # 3. Create Access Request
        cursor.execute("""
            INSERT INTO access_requests (request_type, patient_id, doctor_id, hospital_id, reason, status, duration_minutes)
            VALUES ('normal', ?, ?, ?, ?, 'pending', ?)
        """, (pat["id"], doc["doctor_id"], doc["hospital_id"], reason, duration_minutes))
        request_id = cursor.lastrowid
        db.commit()

        # 4. Spawn OS Process (Medium Priority)
        pid = os_engine.spawn_process(f"Normal Access Req #{request_id}", "MEDIUM", "ACCESS_REQUEST", f"{doc['doctor_name']} -> {health_id}")

        # 5. Log in Audit Journal
        AuditService.log_action(
            actor_name=doc["doctor_name"],
            actor_role="doctor",
            action="REQUEST_NORMAL_ACCESS",
            target_type="patient",
            target_id=health_id,
            details=f"Reason: {reason}, Requested Duration: {duration_minutes}m (PID {pid})",
            actor_id=doctor_user_id
        )

        # 6. Send Real-Time Notification to Patient
        notif_msg = f"{doc['hospital_name']} ({doc['doctor_name']}) is requesting access to your medical records for: '{reason}'"
        NotificationService.send_notification(
            user_id=pat["user_id"],
            notification_type="normal_request",
            title="🔐 Hospital Access Request",
            message=notif_msg,
            data={
                "request_id": request_id,
                "doctor_name": doc["doctor_name"],
                "hospital_name": doc["hospital_name"],
                "reason": reason,
                "duration_minutes": duration_minutes,
                "health_id": health_id
            }
        )

        return {
            "request_id": request_id,
            "status": "pending",
            "message": "Access request submitted. Waiting for patient approval."
        }

    @staticmethod
    def approve_request(request_id: int, patient_user_id: int):
        db = get_db()
        cursor = db.cursor()
        
        # Verify request belongs to patient
        cursor.execute("""
            SELECT r.*, p.user_id as patient_user_id, p.health_id, u.full_name as patient_name,
                   d.doctor_name, d.user_id as doctor_user_id, h.name as hospital_name
            FROM access_requests r
            JOIN patients p ON r.patient_id = p.id
            JOIN users u ON p.user_id = u.id
            JOIN doctors d ON r.doctor_id = d.id
            JOIN hospitals h ON r.hospital_id = h.id
            WHERE r.id = ?
        """, (request_id,))
        req = cursor.fetchone()
        if not req:
            raise ValueError("Access request not found")

        if req["patient_user_id"] != patient_user_id:
            raise PermissionError("Unauthorized: You do not have permission to approve this request")

        if req["status"] != "pending":
            raise ValueError(f"Request cannot be approved: current status is '{req['status']}'")

        # Generate temporary access session token
        session_token = generate_session_token()
        now = datetime.now()
        duration = req["duration_minutes"] or 15
        expires_at = now + timedelta(minutes=duration)

        # Atomic Transaction
        cursor.execute("UPDATE access_requests SET status = 'approved', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (request_id,))
        
        cursor.execute("""
            INSERT INTO access_sessions (request_id, patient_id, doctor_id, session_token, access_type, started_at, expires_at, is_active)
            VALUES (?, ?, ?, ?, 'normal', ?, ?, 1)
        """, (request_id, req["patient_id"], req["doctor_id"], session_token, now.strftime("%Y-%m-%d %H:%M:%S"), expires_at.strftime("%Y-%m-%d %H:%M:%S")))
        session_id = cursor.lastrowid
        db.commit()

        # Acquire OS Mutex Resource Lock on Patient Medical Records
        os_engine.acquire_resource_lock(
            resource_id=f"patient_records_{req['patient_id']}",
            holder_name=f"{req['doctor_name']} ({req['hospital_name']})",
            session_id=str(session_id),
            mode="SHARED_READ"
        )

        # Log in Audit Trail
        AuditService.log_action(
            actor_name=req["patient_name"],
            actor_role="patient",
            action="APPROVE_NORMAL_ACCESS",
            target_type="access_request",
            target_id=str(request_id),
            details=f"Granted {duration}m access to {req['doctor_name']} (Session #{session_id})",
            actor_id=patient_user_id
        )

        # Notify Doctor via Real-Time Event Bus
        NotificationService.broadcast_to_user(req["doctor_user_id"], "access_approved", {
            "request_id": request_id,
            "session_id": session_id,
            "session_token": session_token,
            "patient_id": req["patient_id"],
            "health_id": req["health_id"],
            "patient_name": req["patient_name"],
            "duration_minutes": duration,
            "expires_at": expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            "message": f"Access approved by {req['patient_name']} for {duration} minutes."
        })

        return {
            "status": "approved",
            "session_id": session_id,
            "expires_at": expires_at.strftime("%Y-%m-%d %H:%M:%S")
        }

    @staticmethod
    def reject_request(request_id: int, patient_user_id: int):
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT r.*, p.user_id as patient_user_id, u.full_name as patient_name,
                   d.user_id as doctor_user_id, d.doctor_name
            FROM access_requests r
            JOIN patients p ON r.patient_id = p.id
            JOIN users u ON p.user_id = u.id
            JOIN doctors d ON r.doctor_id = d.id
            WHERE r.id = ?
        """, (request_id,))
        req = cursor.fetchone()
        if not req:
            raise ValueError("Access request not found")

        if req["patient_user_id"] != patient_user_id:
            raise PermissionError("Unauthorized")

        cursor.execute("UPDATE access_requests SET status = 'rejected', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (request_id,))
        db.commit()

        AuditService.log_action(
            actor_name=req["patient_name"],
            actor_role="patient",
            action="REJECT_NORMAL_ACCESS",
            target_type="access_request",
            target_id=str(request_id),
            details=f"Rejected access request from {req['doctor_name']}",
            actor_id=patient_user_id
        )

        # Notify Doctor
        NotificationService.broadcast_to_user(req["doctor_user_id"], "access_rejected", {
            "request_id": request_id,
            "message": "Access request was declined by patient."
        })

        return {"status": "rejected"}

    @staticmethod
    def revoke_session(session_id: int, revoker_user_id: int):
        """Immediately revokes an active access session and locks doctor screen."""
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT s.*, p.user_id as patient_user_id, p.health_id, u.full_name as patient_name,
                   d.user_id as doctor_user_id, d.doctor_name, h.name as hospital_name
            FROM access_sessions s
            JOIN patients p ON s.patient_id = p.id
            JOIN users u ON p.user_id = u.id
            JOIN doctors d ON s.doctor_id = d.id
            JOIN hospitals h ON d.hospital_id = h.id
            WHERE s.id = ?
        """, (session_id,))
        sess = cursor.fetchone()
        if not sess:
            raise ValueError("Session not found")

        # Deactivate session
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            UPDATE access_sessions 
            SET is_active = 0, revoked_at = ?, revoked_by_user_id = ? 
            WHERE id = ?
        """, (now_str, revoker_user_id, session_id))
        
        cursor.execute("UPDATE access_requests SET status = 'revoked' WHERE id = ?", (sess["request_id"],))
        db.commit()

        # Release Mutex Resource Lock
        os_engine.release_resource_lock(f"patient_records_{sess['patient_id']}")

        # Log Audit Trail
        AuditService.log_action(
            actor_name=sess["patient_name"],
            actor_role="patient",
            action="REVOKE_ACCESS_SESSION",
            target_type="access_session",
            target_id=str(session_id),
            details=f"Manually revoked {sess['access_type']} access session for {sess['doctor_name']}",
            actor_id=revoker_user_id
        )

        # Real-time WebSocket / SSE broadcast to Doctor to IMMEDIATELY lock the screen
        NotificationService.broadcast_to_user(sess["doctor_user_id"], "access_revoked", {
            "session_id": session_id,
            "patient_id": sess["patient_id"],
            "health_id": sess["health_id"],
            "message": "Access to patient records has been revoked by the patient."
        })

        return {"status": "revoked", "session_id": session_id}

    @staticmethod
    def get_active_sessions_for_patient(patient_id: int):
        """Fetches active sessions and checks expiration."""
        db = get_db()
        cursor = db.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Deactivate expired sessions
        cursor.execute("""
            UPDATE access_sessions 
            SET is_active = 0 
            WHERE patient_id = ? AND is_active = 1 AND expires_at < ?
        """, (patient_id, now_str))
        db.commit()

        cursor.execute("""
            SELECT s.*, d.doctor_name, d.specialty, h.name as hospital_name
            FROM access_sessions s
            JOIN doctors d ON s.doctor_id = d.id
            JOIN hospitals h ON d.hospital_id = h.id
            WHERE s.patient_id = ? AND s.is_active = 1
            ORDER BY s.id DESC
        """, (patient_id,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_active_session_by_token(token: str):
        db = get_db()
        cursor = db.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            SELECT s.*, p.health_id, p.blood_group, p.allergies, p.existing_conditions, p.current_medications,
                   u.full_name as patient_name, d.doctor_name, h.name as hospital_name
            FROM access_sessions s
            JOIN patients p ON s.patient_id = p.id
            JOIN users u ON p.user_id = u.id
            JOIN doctors d ON s.doctor_id = d.id
            JOIN hospitals h ON d.hospital_id = h.id
            WHERE s.session_token = ? AND s.is_active = 1 AND s.expires_at > ?
        """, (token, now_str))
        row = cursor.fetchone()
        return dict(row) if row else None
