"""
MediFamily OS - Database Seeder
Populates initial demo accounts, fictional medical records, and family hierarchy.
"""

import os
import sqlite3
from datetime import datetime
from backend.app.database import init_db, DB_PATH
from backend.app.auth import hash_password
from backend.app.services.record_service import RecordService
from backend.app.services.audit_service import AuditService

def seed_database():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # Clear existing demo data cleanly
    cursor.execute("DELETE FROM notifications")
    cursor.execute("DELETE FROM audit_logs")
    cursor.execute("DELETE FROM access_sessions")
    cursor.execute("DELETE FROM access_requests")
    cursor.execute("DELETE FROM medical_records")
    cursor.execute("DELETE FROM doctors")
    cursor.execute("DELETE FROM hospitals")
    cursor.execute("DELETE FROM patients")
    cursor.execute("DELETE FROM families")
    cursor.execute("DELETE FROM users")
    conn.commit()

    # 1. Create Family
    cursor.execute("""
        INSERT INTO families (id, family_name, primary_contact)
        VALUES (1, 'Kumar Family', '+91 98765 43210')
    """)

    # 2. Create Users
    users_data = [
        ("ravi", "demo123", "patient", "Ravi Kumar", "ravi.kumar@example.com", "+91 98765 43210"),
        ("priya", "demo123", "patient", "Priya Kumar", "priya.kumar@example.com", "+91 98765 43211"),
        ("arjun", "demo123", "patient", "Arjun Kumar", "arjun.kumar@example.com", "+91 98765 43212"),
        ("arun", "demo123", "doctor", "Dr. Arun", "dr.arun@apollodemo.com", "+91 94440 12345"),
        ("admin", "admin123", "admin", "System Administrator", "admin@medifamily.os", "+91 90000 00000")
    ]

    for username, pwd, role, name, email, phone in users_data:
        pwd_hash = hash_password(pwd)
        cursor.execute("""
            INSERT INTO users (username, password_hash, role, full_name, email, phone)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (username, pwd_hash, role, name, email, phone))
    conn.commit()

    # 3. Create Patients (Kumar Family)
    # Get user IDs
    cursor.execute("SELECT id, username FROM users")
    user_map = {row[1]: row[0] for row in cursor.fetchall()}

    patients_data = [
        (user_map["ravi"], 1, "MF-2026-RAVI01", "Father", "O+", "Penicillin", "Asthma, Mild Hypertension", "Salbutamol Inhaler 100mcg, Amlodipine 5mg", "Priya Kumar", "+91 98765 43211", "1982-05-14", "Male"),
        (user_map["priya"], 1, "MF-2026-PRIYA1", "Mother", "A+", "None", "None", "Multivitamins daily", "Ravi Kumar", "+91 98765 43210", "1985-09-22", "Female"),
        (user_map["arjun"], 1, "MF-2026-ARJUN1", "Son", "O+", "Peanuts", "None", "None", "Priya Kumar", "+91 98765 43211", "2012-11-05", "Male")
    ]

    for uid, fid, hid, rel, bg, alg, cond, med, ec_name, ec_phone, dob, gen in patients_data:
        cursor.execute("""
            INSERT INTO patients (user_id, family_id, health_id, relationship, blood_group, allergies, existing_conditions, current_medications, emergency_contact_name, emergency_contact_phone, date_of_birth, gender)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, fid, hid, rel, bg, alg, cond, med, ec_name, ec_phone, dob, gen))
    conn.commit()

    # 4. Create Hospital & Doctor
    cursor.execute("""
        INSERT INTO hospitals (id, name, registration_number, address, emergency_phone)
        VALUES (1, 'Apollo Demo Hospital', 'HOSP-TN-2026-778', 'Greams Road, Thousand Lights, Chennai', '1066')
    """)

    cursor.execute("""
        INSERT INTO doctors (user_id, hospital_id, doctor_name, specialty, license_number)
        VALUES (?, 1, 'Dr. Arun', 'Emergency & Trauma Care Specialist', 'TNMC-84920')
    """, (user_map["arun"],))
    conn.commit()

    # Get Ravi's patient ID
    cursor.execute("SELECT id FROM patients WHERE health_id = 'MF-2026-RAVI01'")
    ravi_patient_id = cursor.fetchone()[0]

    # Get Priya's patient ID
    cursor.execute("SELECT id FROM patients WHERE health_id = 'MF-2026-PRIYA1'")
    priya_patient_id = cursor.fetchone()[0]
    conn.close()

    # 5. Create Initial Medical Records with sample mock PDFs/documents
    sample_records = [
        (
            ravi_patient_id,
            "Complete Blood Count (CBC) & Lipid Profile",
            "Blood Report",
            "Hemoglobin: 14.2 g/dL, WBC: 6,800/mcL, Platelets: 240,000/mcL, Fasting Blood Sugar: 94 mg/dL, Total Cholesterol: 185 mg/dL. All baseline parameters within normal clinical limits.",
            "2026-08-15",
            "Dr. Arun / Apollo Diagnostics",
            "cbc_lipid_profile_report.pdf",
            b"%PDF-1.4 [MediFamily OS Demo Record: Ravi Kumar - Complete Blood Count & Lipid Profile Report. All parameters normal.]"
        ),
        (
            ravi_patient_id,
            "Asthma Inhaler & Respiratory Prescription",
            "Prescription",
            "Rx: Salbutamol Inhaler 100mcg (2 puffs SOS for acute bronchospasm), Budecort 200 Inhaler (1 puff twice daily after meals). Avoid NSAIDs and Penicillin class antibiotics.",
            "2026-08-01",
            "Dr. K. Swaminathan (Pulmonology)",
            "asthma_rx_dr_swaminathan.pdf",
            b"%PDF-1.4 [MediFamily OS Demo Record: Ravi Kumar - Pulmonology Prescription for Asthma maintenance.]"
        ),
        (
            ravi_patient_id,
            "Chest X-Ray PA View Digital Scan",
            "X-Ray",
            "Digital Chest Radiograph: Lungs well-expanded, clear bronchovascular markings, no acute consolidation, pleural spaces clear, cardiac silhouette normal in size.",
            "2026-07-20",
            "Apollo Imaging & Radiology",
            "chest_xray_pa_view.pdf",
            b"%PDF-1.4 [MediFamily OS Demo Record: Ravi Kumar - Chest X-Ray PA View Normal.]"
        ),
        (
            ravi_patient_id,
            "Annual Health Checkup & Discharge Summary",
            "Discharge Summary",
            "Comprehensive Executive Health Screening. ECG Normal Sinus Rhythm. Blood Pressure: 124/82 mmHg. Pulse: 72 bpm. Patient advised regular aerobic exercise and low sodium diet.",
            "2026-06-10",
            "Apollo Demo Hospital",
            "annual_health_summary_2026.pdf",
            b"%PDF-1.4 [MediFamily OS Demo Record: Ravi Kumar - Annual Executive Health Checkup Summary.]"
        ),
        (
            priya_patient_id,
            "Routine Thyroid & Vitamin D3 Profile",
            "Lab Report",
            "TSH: 2.1 mIU/L (Normal: 0.4 - 4.0), Vitamin D3: 38 ng/mL (Optimal), Vitamin B12: 410 pg/mL.",
            "2026-07-12",
            "City Diagnostics Chennai",
            "thyroid_vitamin_report.pdf",
            b"%PDF-1.4 [MediFamily OS Demo Record: Priya Kumar - Routine Lab Report.]"
        )
    ]

    for pid, title, cat, desc, rdate, doc_hosp, fname, fbytes in sample_records:
        RecordService.add_record(
            patient_id=pid,
            title=title,
            category=cat,
            description=desc,
            record_date=rdate,
            doctor_or_hospital=doc_hosp,
            filename=fname,
            file_bytes=fbytes,
            file_type="application/pdf"
        )

    # 6. Initial Audit Log
    AuditService.log_action(
        actor_name="System Initializer",
        actor_role="admin",
        action="SYSTEM_INIT_SEED",
        target_type="database",
        target_id="medifamily.db",
        details="Seeded Kumar Family (3 members), Apollo Demo Hospital, Dr. Arun, and demo medical records."
    )

    print(">>> MediFamily OS database seeded successfully with demo accounts!")

if __name__ == "__main__":
    seed_database()
