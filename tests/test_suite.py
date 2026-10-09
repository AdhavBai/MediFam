"""
MediFamily OS - Comprehensive Automated Test Suite
Verifies:
1. Authentication & JWT Validation
2. Normal Access Workflow (Request -> Approve -> Session -> Revoke)
3. Emergency Break-Glass Workflow (First-Approval-Wins Atomic Concurrency)
4. SHA-256 File System Integrity
5. Operating Systems Concepts (Processes, Scheduler, Mutex Locks)
"""

import sys
import os
import unittest
import time
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.database import init_db, get_db
from backend.app.auth import hash_password, verify_password, create_jwt_token, decode_jwt_token
from backend.app.seed import seed_database
from backend.app.services.patient_service import PatientService
from backend.app.services.record_service import RecordService
from backend.app.services.access_service import AccessService
from backend.app.services.emergency_service import EmergencyService
from backend.app.services.notification_service import NotificationService
from backend.app.services.audit_service import AuditService
from backend.app.os_engine import os_engine

class TestMediFamilyOS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_database()

    def test_01_password_and_jwt_auth(self):
        """Verify PBKDF2 hashing and JWT token cryptographic signing."""
        pwd = "securePassword123"
        hashed = hash_password(pwd)
        self.assertTrue(verify_password(pwd, hashed))
        self.assertFalse(verify_password("wrongPass", hashed))

        payload = {"user_id": 1, "username": "ravi", "role": "patient"}
        token = create_jwt_token(payload)
        decoded = decode_jwt_token(token)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded["username"], "ravi")
        self.assertEqual(decoded["role"], "patient")

    def test_02_patient_lookup_and_family(self):
        """Verify Unique Health ID (UHID) resolution and family hierarchy."""
        pat = PatientService.get_patient_by_health_id("MF-2026-RAVI01")
        self.assertIsNotNone(pat)
        self.assertEqual(pat["full_name"], "Ravi Kumar")
        self.assertEqual(pat["blood_group"], "O+")

        # Fetch family members
        members = PatientService.get_family_members(pat["family_id"])
        self.assertEqual(len(members), 3) # Ravi, Priya, Arjun

        # Fetch family overview
        overview = PatientService.get_family_overview(pat["family_id"])
        self.assertEqual(overview["member_count"], 3)
        self.assertGreaterEqual(overview["total_records"], 4)

    def test_03_medical_record_sha256_integrity(self):
        """Verify file upload, encrypted storage, and SHA-256 cryptographic verification."""
        pat = PatientService.get_patient_by_health_id("MF-2026-RAVI01")
        test_file_bytes = b"Sample Ultrasound Scan Data 2026 for Ravi Kumar"
        
        record_id = RecordService.add_record(
            patient_id=pat["id"],
            title="Abdominal Ultrasound Test",
            category="Scan",
            description="Liver and kidneys normal",
            record_date="2026-09-01",
            doctor_or_hospital="Apollo Imaging",
            filename="ultrasound_test.pdf",
            file_bytes=test_file_bytes
        )
        self.assertIsNotNone(record_id)

        records = RecordService.get_records_by_patient(pat["id"])
        uploaded = next((r for r in records if r["id"] == record_id), None)
        self.assertIsNotNone(uploaded)
        self.assertTrue(uploaded["integrity_verified"])
        self.assertEqual(uploaded["sha256_hash"], os_engine.calculate_file_hash(test_file_bytes))

        # Cleanup
        RecordService.delete_record(record_id, pat["id"])

    def test_04_normal_access_workflow(self):
        """Verify full 7-step Normal Access Workflow: Request -> Approve -> Session -> Revoke."""
        # 1. Doctor requests access
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT user_id FROM doctors WHERE doctor_name = 'Dr. Arun'")
        doc_uid = cursor.fetchone()["user_id"]
        
        cursor.execute("SELECT user_id, id FROM patients WHERE health_id = 'MF-2026-RAVI01'")
        pat_row = cursor.fetchone()
        pat_uid, pat_id = pat_row["user_id"], pat_row["id"]

        req_res = AccessService.create_normal_request(doc_uid, "MF-2026-RAVI01", "Routine Followup", 15)
        self.assertEqual(req_res["status"], "pending")
        req_id = req_res["request_id"]

        # 2. Patient approves access
        app_res = AccessService.approve_request(req_id, pat_uid)
        self.assertEqual(app_res["status"], "approved")
        session_id = app_res["session_id"]

        # 3. Verify active session exists
        active_sessions = AccessService.get_active_sessions_for_patient(pat_id)
        self.assertTrue(any(s["id"] == session_id for s in active_sessions))

        # 4. Patient revokes access
        rev_res = AccessService.revoke_session(session_id, pat_uid)
        self.assertEqual(rev_res["status"], "revoked")

        # 5. Verify session is no longer active
        active_sessions_after = AccessService.get_active_sessions_for_patient(pat_id)
        self.assertFalse(any(s["id"] == session_id for s in active_sessions_after))

    def test_05_emergency_break_glass_first_approval_wins(self):
        """
        Verify Emergency Break-Glass workflow:
        1. Emergency request created with 6-digit verification code.
        2. Family member A approves -> success.
        3. Family member B approves after -> receives 'already_approved' (concurrency synchronization).
        """
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT user_id FROM doctors WHERE doctor_name = 'Dr. Arun'")
        doc_uid = cursor.fetchone()["user_id"]
        
        cursor.execute("SELECT id FROM users WHERE username = 'priya'")
        priya_uid = cursor.fetchone()["id"]
        
        cursor.execute("SELECT id FROM users WHERE username = 'arjun'")
        arjun_uid = cursor.fetchone()["id"]

        # 1. Trigger Emergency Access
        em_res = EmergencyService.create_emergency_request(doc_uid, "MF-2026-RAVI01", "Road Accident Trauma")
        req_id = em_res["request_id"]
        code = em_res["demo_verification_code"]
        self.assertEqual(len(code), 6)

        # 2. Priya Kumar (Mother) verifies and approves code
        verify_a = EmergencyService.verify_and_approve_emergency(req_id, priya_uid, code)
        self.assertEqual(verify_a["status"], "approved")
        session_id = verify_a["session_id"]

        # 3. Arjun Kumar (Son) tries to verify same request -> receives 'already_approved'
        verify_b = EmergencyService.verify_and_approve_emergency(req_id, arjun_uid, code)
        self.assertEqual(verify_b["status"], "already_approved")

        # 4. Fetch Emergency Medical Summary
        summary = EmergencyService.get_emergency_summary("MF-2026-RAVI01")
        self.assertIsNotNone(summary)
        self.assertEqual(summary["blood_group"], "O+")
        self.assertEqual(summary["allergies"], "Penicillin")

    def test_06_os_concepts_engine(self):
        """Verify OS Concepts: Process table, Priority Scheduler queue, and Mutex Locks."""
        procs = os_engine.get_process_table()
        self.assertGreater(len(procs), 0)

        queue = os_engine.get_scheduler_queue()
        self.assertIn("high_priority_queue", queue)
        self.assertIn("medium_priority_queue", queue)
        self.assertIn("low_priority_queue", queue)

        # Test Mutex Locking
        lock_res1 = os_engine.acquire_resource_lock("res_test_101", "Dr. Arun", "sess_99")
        self.assertTrue(lock_res1)

        # Lock contention: second acquire must fail
        lock_res2 = os_engine.acquire_resource_lock("res_test_101", "Dr. Sharma", "sess_100")
        self.assertFalse(lock_res2)

        # Release lock
        os_engine.release_resource_lock("res_test_101")
        lock_res3 = os_engine.acquire_resource_lock("res_test_101", "Dr. Sharma", "sess_100")
        self.assertTrue(lock_res3)
        os_engine.release_resource_lock("res_test_101")

if __name__ == "__main__":
    unittest.main()
