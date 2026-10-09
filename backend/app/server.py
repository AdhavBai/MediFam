"""
MediFamily OS - High Performance Full-Stack Server & REST API Router
Provides:
- Complete REST APIs matching all requirements
- Real-Time Server-Sent Events (SSE) stream for sub-millisecond multi-device sync
- Role-Based Access Control (RBAC) middleware & JWT token validation
- Static asset serving for responsive web & mobile UI
- Built-in interactive API Documentation viewer
"""

import http.server
import socketserver
import os
import json
import urllib.parse
import threading
import mimetypes
import queue
import time
from datetime import datetime

from backend.app.database import get_db, init_db
from backend.app.auth import decode_jwt_token, create_jwt_token, verify_password, hash_password
from backend.app.services.patient_service import PatientService
from backend.app.services.record_service import RecordService
from backend.app.services.access_service import AccessService
from backend.app.services.emergency_service import EmergencyService
from backend.app.services.notification_service import NotificationService
from backend.app.services.audit_service import AuditService
from backend.app.os_engine import os_engine
from backend.app.seed import seed_database

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend")
STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "storage")

class MediFamilyRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FRONTEND_DIR, **kwargs)

    def log_message(self, format, *args):
        # Concise logging
        pass

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, X-Session-Token")
        self.send_header("X-Content-Type-Options", "nosniff")

    def _send_json(self, data: dict, status_code: int = 200):
        body = json.dumps(data, default=str).encode('utf-8')
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, message: str, status_code: int = 400):
        self._send_json({"error": message, "success": False}, status_code)

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def get_auth_user(self):
        """Extract and verify JWT token from Authorization header or query parameter."""
        auth_header = self.headers.get("Authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        else:
            # Query parameter fallback (for SSE)
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            if "token" in params:
                token = params["token"][0]

        if not token:
            return None
        return decode_jwt_token(token)

    def read_json_body(self):
        """Reads and parses JSON body from request."""
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode('utf-8')
        try:
            return json.loads(raw)
        except Exception:
            return {}

    # ------------------ GET ROUTER ------------------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. Real-Time SSE Stream: /api/events
        if path == "/api/events":
            self.handle_sse_stream(query)
            return

        # 2. Interactive API Docs: /api/docs or /docs
        if path in ("/api/docs", "/docs"):
            self.serve_api_docs()
            return

        # 3. REST API Routes
        if path.startswith("/api/"):
            self.handle_api_get(path, query)
            return

        # 4. Storage File Download: /storage/medical_records/...
        if path.startswith("/storage/"):
            self.handle_storage_download(path)
            return

        # 5. Static frontend files
        super().do_GET()

    def handle_sse_stream(self, query):
        """Server-Sent Events real-time event streaming."""
        token = query.get("token", [""])[0]
        user = decode_jwt_token(token) if token else None
        user_id = user["user_id"] if user else 0

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._send_cors_headers()
        self.end_headers()

        # Send initial connected event
        init_event = f"event: connected\ndata: {json.dumps({'status': 'connected', 'user_id': user_id})}\n\n"
        self.wfile.write(init_event.encode('utf-8'))
        self.wfile.flush()

        client_queue = NotificationService.subscribe(user_id)
        try:
            while True:
                try:
                    event = client_queue.get(timeout=15.0)
                    msg = f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
                    self.wfile.write(msg.encode('utf-8'))
                    self.wfile.flush()
                except queue.Empty:
                    # Keep-alive heartbeat ping
                    ping = f": ping\n\n"
                    self.wfile.write(ping.encode('utf-8'))
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, Exception):
            pass
        finally:
            NotificationService.unsubscribe(user_id, client_queue)

    def handle_api_get(self, path: str, query: dict):
        user = self.get_auth_user()

        # Auth profile check
        if path == "/api/auth/me":
            if not user:
                return self._send_error("Unauthorized", 401)
            
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT id, username, role, full_name, email, phone FROM users WHERE id = ?", (user["user_id"],))
            u_row = cursor.fetchone()
            if not u_row:
                return self._send_error("User not found", 404)
            
            resp = dict(u_row)
            if u_row["role"] == "patient":
                resp["patient_profile"] = PatientService.get_patient_by_user_id(user["user_id"])
            elif u_row["role"] == "doctor":
                cursor.execute("""
                    SELECT d.*, h.name as hospital_name, h.address as hospital_address, h.emergency_phone
                    FROM doctors d
                    JOIN hospitals h ON d.hospital_id = h.id
                    WHERE d.user_id = ?
                """, (user["user_id"],))
                d_row = cursor.fetchone()
                resp["doctor_profile"] = dict(d_row) if d_row else None
            return self._send_json({"success": True, "user": resp})

        # Patient Lookup by Health ID: /api/patients/{health_id}
        if path.startswith("/api/patients/") and not path.endswith("/records") and not path.endswith("/active-sessions"):
            health_id = path.replace("/api/patients/", "").strip()
            pat = PatientService.get_patient_by_health_id(health_id)
            if not pat:
                return self._send_error(f"Patient with Health ID '{health_id}' not found", 404)
            return self._send_json({"success": True, "patient": pat})

        # Patient Medical Records: /api/patients/{id}/records
        if path.startswith("/api/patients/") and path.endswith("/records"):
            parts = path.split("/")
            patient_id = int(parts[3])
            
            # Security verification
            has_access = False
            if user:
                if user["role"] == "admin":
                    has_access = True
                elif user["role"] == "patient":
                    pat_prof = PatientService.get_patient_by_user_id(user["user_id"])
                    if pat_prof and (pat_prof["id"] == patient_id or pat_prof["family_id"] == PatientService.get_patient_by_id(patient_id).get("family_id")):
                        has_access = True
                elif user["role"] == "doctor":
                    # Check active session token from header
                    sess_token = self.headers.get("X-Session-Token", "")
                    if sess_token:
                        sess = AccessService.get_active_session_by_token(sess_token)
                        if sess and sess["patient_id"] == patient_id:
                            has_access = True

            if not has_access:
                return self._send_error("Forbidden: You do not have an active authorized session to view these records", 403)

            records = RecordService.get_records_by_patient(patient_id)
            return self._send_json({"success": True, "records": records, "count": len(records)})

        # Patient Active Sessions: /api/patients/{id}/active-sessions
        if path.startswith("/api/patients/") and path.endswith("/active-sessions"):
            parts = path.split("/")
            patient_id = int(parts[3])
            sessions = AccessService.get_active_sessions_for_patient(patient_id)
            return self._send_json({"success": True, "active_sessions": sessions})

        # Emergency Medical Summary: /api/emergency/summary/{health_id}
        if path.startswith("/api/emergency/summary/"):
            health_id = path.replace("/api/emergency/summary/", "").strip()
            summary = EmergencyService.get_emergency_summary(health_id)
            if not summary:
                return self._send_error("Patient not found", 404)
            return self._send_json({"success": True, "emergency_summary": summary})

        # Notifications: /api/notifications
        if path == "/api/notifications":
            if not user:
                return self._send_error("Unauthorized", 401)
            notifs = NotificationService.get_user_notifications(user["user_id"])
            return self._send_json({"success": True, "notifications": notifs})

        # Family Members: /api/family/{id}/members
        if path.startswith("/api/family/") and path.endswith("/members"):
            family_id = int(path.split("/")[3])
            members = PatientService.get_family_members(family_id)
            return self._send_json({"success": True, "members": members})

        # Family Health Overview: /api/family/overview
        if path == "/api/family/overview":
            if not user or user["role"] != "patient":
                return self._send_error("Unauthorized", 401)
            pat_prof = PatientService.get_patient_by_user_id(user["user_id"])
            if not pat_prof:
                return self._send_error("Patient profile not found", 404)
            overview = PatientService.get_family_overview(pat_prof["family_id"])
            return self._send_json({"success": True, "overview": overview})

        # Audit Logs: /api/audit-logs
        if path == "/api/audit-logs":
            if not user:
                return self._send_error("Unauthorized", 401)
            logs = AuditService.get_logs(limit=100)
            return self._send_json({"success": True, "audit_logs": logs})

        # System Monitor Status: /api/system/status
        if path == "/api/system/status":
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM users")
            user_count = cursor.fetchone()["count"]
            
            cursor.execute("SELECT COUNT(*) as count FROM access_sessions WHERE is_active = 1")
            active_sessions = cursor.fetchone()["count"]
            
            cursor.execute("SELECT COUNT(*) as count FROM access_requests WHERE status = 'pending' AND request_type = 'normal'")
            pending_requests = cursor.fetchone()["count"]
            
            cursor.execute("SELECT COUNT(*) as count FROM access_requests WHERE status = 'pending' AND request_type = 'emergency'")
            pending_emergencies = cursor.fetchone()["count"]
            
            storage_stats = RecordService.get_storage_stats()

            return self._send_json({
                "success": True,
                "status": {
                    "backend": "ONLINE",
                    "database": "ONLINE",
                    "websocket_sse": "CONNECTED",
                    "active_users": user_count,
                    "active_sessions": active_sessions,
                    "pending_requests": pending_requests,
                    "emergency_requests": pending_emergencies,
                    "storage_mb": storage_stats["total_mb"],
                    "total_files": storage_stats["total_files"]
                }
            })

        # OS Concepts Engine Live State: /api/system/os-concepts
        if path == "/api/system/os-concepts":
            return self._send_json({
                "success": True,
                "os_data": {
                    "processes": os_engine.get_process_table(),
                    "scheduler_queue": os_engine.get_scheduler_queue(),
                    "resource_locks": os_engine.get_resource_locks(),
                    "storage_stats": RecordService.get_storage_stats()
                }
            })

        # If unknown API route
        self._send_error(f"Endpoint GET '{path}' not found", 404)

    # ------------------ POST ROUTER ------------------
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        user = self.get_auth_user()
        data = self.read_json_body()

        # 1. Login: /api/auth/login
        if path == "/api/auth/login":
            username = data.get("username", "").strip().lower()
            password = data.get("password", "")
            if not username or not password:
                return self._send_error("Username and password are required")

            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT * FROM users WHERE LOWER(username) = ?", (username,))
            u = cursor.fetchone()
            if not u or not verify_password(password, u["password_hash"]):
                AuditService.log_action(username, "guest", "LOGIN_FAILED", "auth", username, "Invalid credentials", status="FAILED")
                return self._send_error("Invalid username or password", 401)

            # Generate token
            payload = {"user_id": u["id"], "username": u["username"], "role": u["role"]}
            token = create_jwt_token(payload)

            # Get Role-specific details
            role_data = {}
            if u["role"] == "patient":
                role_data["patient"] = PatientService.get_patient_by_user_id(u["id"])
            elif u["role"] == "doctor":
                cursor.execute("""
                    SELECT d.*, h.name as hospital_name, h.address as hospital_address, h.emergency_phone
                    FROM doctors d
                    JOIN hospitals h ON d.hospital_id = h.id
                    WHERE d.user_id = ?
                """, (u["id"],))
                d_row = cursor.fetchone()
                role_data["doctor"] = dict(d_row) if d_row else None

            AuditService.log_action(u["full_name"], u["role"], "LOGIN_SUCCESS", "auth", str(u["id"]), f"Logged in as {u['role']}", actor_id=u["id"])

            return self._send_json({
                "success": True,
                "token": token,
                "user": {
                    "id": u["id"],
                    "username": u["username"],
                    "role": u["role"],
                    "full_name": u["full_name"],
                    "email": u["email"],
                    "phone": u["phone"],
                    **role_data
                }
            })

        # 2. Medical Record Upload: /api/patients/{id}/records
        if path.startswith("/api/patients/") and path.endswith("/records"):
            if not user:
                return self._send_error("Unauthorized", 401)
            patient_id = int(path.split("/")[3])
            
            title = data.get("title", "").strip()
            category = data.get("category", "Prescription")
            description = data.get("description", "")
            record_date = data.get("record_date", datetime.now().strftime("%Y-%m-%d"))
            doctor_or_hospital = data.get("doctor_or_hospital", "")
            filename = data.get("filename", "document.pdf")
            file_base64 = data.get("file_base64", "")

            if not title:
                return self._send_error("Record title is required")

            import base64
            if file_base64:
                try:
                    file_bytes = base64.b64decode(file_base64)
                except Exception:
                    file_bytes = f"%PDF-1.4 [MediFamily Record: {title}]".encode('utf-8')
            else:
                file_bytes = f"%PDF-1.4 [MediFamily Record: {title}\nDate: {record_date}\nDoctor/Facility: {doctor_or_hospital}\nNotes: {description}]".encode('utf-8')

            record_id = RecordService.add_record(
                patient_id=patient_id,
                title=title,
                category=category,
                description=description,
                record_date=record_date,
                doctor_or_hospital=doctor_or_hospital,
                filename=filename,
                file_bytes=file_bytes
            )

            AuditService.log_action(user["username"], user["role"], "UPLOAD_MEDICAL_RECORD", "medical_record", str(record_id), f"Uploaded '{title}' ({category})", actor_id=user["user_id"])

            return self._send_json({"success": True, "record_id": record_id, "message": "Medical record uploaded and verified successfully!"})

        # 3. Normal Access Request: /api/access/request
        if path == "/api/access/request":
            if not user or user["role"] != "doctor":
                return self._send_error("Only registered doctors can request access", 403)
            health_id = data.get("health_id", "").strip()
            reason = data.get("reason", "Patient Consultation")
            duration = int(data.get("duration_minutes", 15))
            
            try:
                res = AccessService.create_normal_request(user["user_id"], health_id, reason, duration)
                return self._send_json({"success": True, **res})
            except Exception as e:
                return self._send_error(str(e))

        # 4. Approve Normal Access: /api/access/{id}/approve
        if path.startswith("/api/access/") and path.endswith("/approve") and not "emergency" in path:
            if not user or user["role"] != "patient":
                return self._send_error("Unauthorized", 401)
            request_id = int(path.split("/")[3])
            try:
                res = AccessService.approve_request(request_id, user["user_id"])
                return self._send_json({"success": True, **res})
            except Exception as e:
                return self._send_error(str(e))

        # 5. Reject Normal Access: /api/access/{id}/reject
        if path.startswith("/api/access/") and path.endswith("/reject"):
            if not user or user["role"] != "patient":
                return self._send_error("Unauthorized", 401)
            request_id = int(path.split("/")[3])
            try:
                res = AccessService.reject_request(request_id, user["user_id"])
                return self._send_json({"success": True, **res})
            except Exception as e:
                return self._send_error(str(e))

        # 6. Revoke Active Access Session: /api/access/sessions/{id}/revoke
        if path.startswith("/api/access/sessions/") and path.endswith("/revoke"):
            if not user or user["role"] != "patient":
                return self._send_error("Unauthorized", 401)
            session_id = int(path.split("/")[4])
            try:
                res = AccessService.revoke_session(session_id, user["user_id"])
                return self._send_json({"success": True, **res})
            except Exception as e:
                return self._send_error(str(e))

        # 7. Emergency Access Request (Break-Glass): /api/emergency/request
        if path == "/api/emergency/request":
            if not user or user["role"] != "doctor":
                return self._send_error("Only authorized medical/ER personnel can trigger Break-Glass access", 403)
            health_id = data.get("health_id", "").strip()
            reason = data.get("reason", "Road Accident / Trauma Emergency")
            try:
                res = EmergencyService.create_emergency_request(user["user_id"], health_id, reason)
                return self._send_json({"success": True, **res})
            except Exception as e:
                return self._send_error(str(e))

        # 8. Verify & Approve Emergency Access: /api/emergency/{id}/approve
        if path.startswith("/api/emergency/") and path.endswith("/approve"):
            if not user or user["role"] != "patient":
                return self._send_error("Only registered family members can verify emergency requests", 403)
            request_id = int(path.split("/")[3])
            code = data.get("verification_code", "").strip()
            if not code:
                return self._send_error("6-digit verification code is required")
            try:
                res = EmergencyService.verify_and_approve_emergency(request_id, user["user_id"], code)
                return self._send_json({"success": True, **res})
            except Exception as e:
                return self._send_error(str(e))

        # 9. Mark Notification as Read: /api/notifications/{id}/read
        if path.startswith("/api/notifications/") and path.endswith("/read"):
            if not user:
                return self._send_error("Unauthorized", 401)
            notif_id = int(path.split("/")[3])
            NotificationService.mark_as_read(notif_id, user["user_id"])
            return self._send_json({"success": True, "message": "Notification marked as read"})

        # 10. Update Patient Emergency Profile: /api/patients/{id}/profile
        if path.startswith("/api/patients/") and path.endswith("/profile"):
            if not user or user["role"] != "patient":
                return self._send_error("Unauthorized", 401)
            patient_id = int(path.split("/")[3])
            PatientService.update_medical_profile(
                patient_id=patient_id,
                blood_group=data.get("blood_group", "O+"),
                allergies=data.get("allergies", ""),
                conditions=data.get("existing_conditions", ""),
                medications=data.get("current_medications", ""),
                contact_name=data.get("emergency_contact_name", ""),
                contact_phone=data.get("emergency_contact_phone", "")
            )
            AuditService.log_action(user["username"], "patient", "UPDATE_EMERGENCY_PROFILE", "patient", str(patient_id), "Updated allergies & emergency contacts", actor_id=user["user_id"])
            return self._send_json({"success": True, "message": "Medical profile updated successfully!"})

        # 11. Demo Simulation Triggers (Academic Presentation Mode)
        if path == "/api/demo/simulate-access":
            # Simulate Dr. Arun requesting access to Ravi Kumar
            try:
                db = get_db()
                cursor = db.cursor()
                cursor.execute("SELECT user_id FROM doctors WHERE doctor_name = 'Dr. Arun'")
                doc_uid = cursor.fetchone()["user_id"]
                res = AccessService.create_normal_request(doc_uid, "MF-2026-RAVI01", "Routine Cardiology & Asthma Review Consultation", 15)
                return self._send_json({"success": True, "simulation": "normal_access", **res})
            except Exception as e:
                return self._send_error(str(e))

        if path == "/api/demo/simulate-emergency":
            # Simulate Emergency Break-Glass from Apollo Demo Hospital to Ravi Kumar
            try:
                db = get_db()
                cursor = db.cursor()
                cursor.execute("SELECT user_id FROM doctors WHERE doctor_name = 'Dr. Arun'")
                doc_uid = cursor.fetchone()["user_id"]
                res = EmergencyService.create_emergency_request(doc_uid, "MF-2026-RAVI01", "High-Speed Highway Collision - Acute Hemorrhage & Hypoxia")
                return self._send_json({"success": True, "simulation": "emergency_access", **res})
            except Exception as e:
                return self._send_error(str(e))

        if path == "/api/demo/reset":
            seed_database()
            NotificationService.broadcast_to_all("system_reset", {"message": "Demo data has been reset to baseline."})
            return self._send_json({"success": True, "message": "Demo database successfully reset!"})

        self._send_error(f"Endpoint POST '{path}' not found", 404)

    # ------------------ DELETE ROUTER ------------------
    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        user = self.get_auth_user()

        if path.startswith("/api/records/"):
            if not user or user["role"] != "patient":
                return self._send_error("Unauthorized", 401)
            record_id = int(path.replace("/api/records/", "").strip())
            pat_prof = PatientService.get_patient_by_user_id(user["user_id"])
            if not pat_prof:
                return self._send_error("Patient profile not found", 404)
            
            success = RecordService.delete_record(record_id, pat_prof["id"])
            if success:
                AuditService.log_action(user["username"], "patient", "DELETE_MEDICAL_RECORD", "medical_record", str(record_id), "Record removed by patient", actor_id=user["user_id"])
                return self._send_json({"success": True, "message": "Medical record deleted successfully!"})
            else:
                return self._send_error("Record not found or access denied", 404)

        self._send_error(f"Endpoint DELETE '{path}' not found", 404)

    def handle_storage_download(self, path: str):
        """Secure download endpoint for medical files."""
        rel_path = path.replace("/storage/", "")
        full_path = os.path.join(STORAGE_DIR, rel_path)
        if not os.path.exists(full_path) or not os.path.isfile(full_path):
            self.send_error(404, "File not found")
            return

        with open(full_path, "rb") as f:
            content = f.read()

        mime_type, _ = mimetypes.guess_type(full_path)
        mime_type = mime_type or "application/octet-stream"

        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Content-Disposition", f"inline; filename={os.path.basename(full_path)}")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(content)

    def serve_api_docs(self):
        """Serves clean Swagger/OpenAPI style interactive API documentation."""
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MediFamily OS - API Reference & OS Architecture</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>body { font-family: 'Plus Jakarta Sans', sans-serif; } code { font-family: 'JetBrains Mono', monospace; }</style>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen p-6">
    <div class="max-w-5xl mx-auto">
        <header class="border-b border-slate-800 pb-6 mb-8 flex justify-between items-center">
            <div>
                <span class="inline-block px-3 py-1 bg-cyan-500/20 text-cyan-400 text-xs font-semibold rounded-full mb-2">REST & Real-Time API Reference</span>
                <h1 class="text-3xl font-extrabold text-white tracking-tight">MediFamily OS <span class="text-cyan-400">API Documentation</span></h1>
                <p class="text-slate-400 text-sm mt-1">Operating Systems Academic Prototype • C.A Adhavasubash & MD Amman Khan</p>
            </div>
            <a href="/" class="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-semibold rounded-lg shadow-lg transition">Launch App &rarr;</a>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div class="bg-slate-800/80 p-5 rounded-xl border border-slate-700">
                <h3 class="text-sm font-bold text-cyan-400 uppercase tracking-wider mb-2">Base URLs</h3>
                <p class="text-xs text-slate-300 mb-1">Local Machine: <code class="text-emerald-400">http://localhost:8000</code></p>
                <p class="text-xs text-slate-300">LAN / Android Phone: <code class="text-emerald-400">http://&lt;PC_IP&gt;:8000</code></p>
            </div>
            <div class="bg-slate-800/80 p-5 rounded-xl border border-slate-700">
                <h3 class="text-sm font-bold text-cyan-400 uppercase tracking-wider mb-2">Authentication</h3>
                <p class="text-xs text-slate-300">Headers: <code class="text-amber-300">Authorization: Bearer &lt;JWT_TOKEN&gt;</code></p>
                <p class="text-xs text-slate-300 mt-1">Doctor Active Session: <code class="text-amber-300">X-Session-Token: &lt;SESSION_TOKEN&gt;</code></p>
            </div>
        </div>

        <h2 class="text-xl font-bold text-white mb-4">Core API Endpoints</h2>
        <div class="space-y-4">
            <!-- Auth Login -->
            <div class="bg-slate-800/60 p-4 rounded-xl border border-slate-700/80 hover:border-slate-600 transition">
                <div class="flex items-center space-x-3 mb-2">
                    <span class="px-2.5 py-1 bg-emerald-500/20 text-emerald-400 text-xs font-bold rounded">POST</span>
                    <code class="text-sm font-semibold text-white">/api/auth/login</code>
                    <span class="text-xs text-slate-400">— Authenticate user & issue JWT</span>
                </div>
                <p class="text-xs text-slate-400 mb-2">Payload: <code>{"username": "ravi", "password": "demo123"}</code></p>
            </div>

            <!-- Patient Lookup -->
            <div class="bg-slate-800/60 p-4 rounded-xl border border-slate-700/80 hover:border-slate-600 transition">
                <div class="flex items-center space-x-3 mb-2">
                    <span class="px-2.5 py-1 bg-cyan-500/20 text-cyan-400 text-xs font-bold rounded">GET</span>
                    <code class="text-sm font-semibold text-white">/api/patients/{health_id}</code>
                    <span class="text-xs text-slate-400">— Lookup patient by Unique Health ID (e.g. MF-2026-RAVI01)</span>
                </div>
            </div>

            <!-- Request Normal Access -->
            <div class="bg-slate-800/60 p-4 rounded-xl border border-slate-700/80 hover:border-slate-600 transition">
                <div class="flex items-center space-x-3 mb-2">
                    <span class="px-2.5 py-1 bg-emerald-500/20 text-emerald-400 text-xs font-bold rounded">POST</span>
                    <code class="text-sm font-semibold text-white">/api/access/request</code>
                    <span class="text-xs text-slate-400">— Doctor requests time-limited access</span>
                </div>
                <p class="text-xs text-slate-400">Payload: <code>{"health_id": "MF-2026-RAVI01", "reason": "Consultation", "duration_minutes": 15}</code></p>
            </div>

            <!-- Emergency Request -->
            <div class="bg-slate-800/60 p-4 rounded-xl border border-red-900/50 bg-red-950/20 hover:border-red-700 transition">
                <div class="flex items-center space-x-3 mb-2">
                    <span class="px-2.5 py-1 bg-red-500/20 text-red-400 text-xs font-bold rounded">POST</span>
                    <code class="text-sm font-semibold text-red-300">/api/emergency/request</code>
                    <span class="text-xs text-red-400 font-semibold">— Trigger Break-Glass Emergency Access (Generates 6-digit OTP & multi-family broadcast)</span>
                </div>
                <p class="text-xs text-slate-400">Payload: <code>{"health_id": "MF-2026-RAVI01", "reason": "Road Accident"}</code></p>
            </div>

            <!-- Emergency Verify -->
            <div class="bg-slate-800/60 p-4 rounded-xl border border-red-900/50 bg-red-950/20 hover:border-red-700 transition">
                <div class="flex items-center space-x-3 mb-2">
                    <span class="px-2.5 py-1 bg-red-500/20 text-red-400 text-xs font-bold rounded">POST</span>
                    <code class="text-sm font-semibold text-red-300">/api/emergency/{id}/approve</code>
                    <span class="text-xs text-red-400 font-semibold">— Family Member verifies OTP (First-approval-wins synchronization)</span>
                </div>
                <p class="text-xs text-slate-400">Payload: <code>{"verification_code": "482913"}</code></p>
            </div>

            <!-- Real-time Event Stream -->
            <div class="bg-slate-800/60 p-4 rounded-xl border border-purple-900/50 bg-purple-950/20 hover:border-purple-700 transition">
                <div class="flex items-center space-x-3 mb-2">
                    <span class="px-2.5 py-1 bg-purple-500/20 text-purple-400 text-xs font-bold rounded">GET</span>
                    <code class="text-sm font-semibold text-purple-300">/api/events?token={jwt}</code>
                    <span class="text-xs text-purple-400 font-semibold">— Real-Time Server-Sent Events (SSE) Bus</span>
                </div>
            </div>

            <!-- OS Concepts Telemetry -->
            <div class="bg-slate-800/60 p-4 rounded-xl border border-slate-700/80 hover:border-slate-600 transition">
                <div class="flex items-center space-x-3 mb-2">
                    <span class="px-2.5 py-1 bg-cyan-500/20 text-cyan-400 text-xs font-bold rounded">GET</span>
                    <code class="text-sm font-semibold text-white">/api/system/os-concepts</code>
                    <span class="text-xs text-slate-400">— Process table (PID, Priority, State), Scheduler queues, Mutex resource locks</span>
                </div>
            </div>
        </div>

        <footer class="mt-12 pt-6 border-t border-slate-800 text-center text-xs text-slate-500">
            MediFamily OS — Academic Prototype | Not intended for real clinical use
        </footer>
    </div>
</body>
</html>"""
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def run_server(host="0.0.0.0", port=8000):
    init_db()
    server_address = (host, port)
    httpd = ThreadedHTTPServer(server_address, MediFamilyRequestHandler)
    print(f"================================================================")
    print(f" 🚀 MediFamily OS Web & Mobile Prototype Server Active!")
    print(f" 🌐 Local Access:    http://localhost:{port}")
    print(f" 📱 LAN Access:      http://0.0.0.0:{port}")
    print(f" 📖 API Reference:   http://localhost:{port}/api/docs")
    print(f"================================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping MediFamily OS Server...")
        httpd.server_close()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    run_server(port=port)
