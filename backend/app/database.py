"""
MediFamily OS - Database Engine & Schema Definition
Relational SQLite database with transaction safety, constraints, and index optimization.
"""

import sqlite3
import os
import threading
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "medifamily.db")

# Thread-local database connection manager
_local = threading.local()

def get_db():
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, timeout=20.0, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA foreign_keys = ON")
        _local.conn.execute("PRAGMA journal_mode = WAL")
    return _local.conn

def close_db():
    if hasattr(_local, "conn") and _local.conn is not None:
        _local.conn.close()
        _local.conn = None

def init_db():
    """Create all required tables, constraints, and indexes."""
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('patient', 'doctor', 'admin')),
        full_name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Families Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS families (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        family_name TEXT NOT NULL,
        primary_contact TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. Patients Table (Family Members)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        family_id INTEGER NOT NULL,
        health_id TEXT UNIQUE NOT NULL,
        relationship TEXT NOT NULL,
        blood_group TEXT NOT NULL,
        allergies TEXT DEFAULT '',
        existing_conditions TEXT DEFAULT '',
        current_medications TEXT DEFAULT '',
        emergency_contact_name TEXT,
        emergency_contact_phone TEXT,
        date_of_birth TEXT,
        gender TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (family_id) REFERENCES families(id) ON DELETE CASCADE
    );
    """)

    # 4. Hospitals Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hospitals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        registration_number TEXT,
        address TEXT,
        emergency_phone TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 5. Doctors Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        hospital_id INTEGER NOT NULL,
        doctor_name TEXT NOT NULL,
        specialty TEXT,
        license_number TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (hospital_id) REFERENCES hospitals(id) ON DELETE CASCADE
    );
    """)

    # 6. Medical Records Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS medical_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT DEFAULT '',
        record_date TEXT NOT NULL,
        doctor_or_hospital TEXT DEFAULT '',
        filename TEXT,
        file_path TEXT,
        file_size_bytes INTEGER DEFAULT 0,
        file_type TEXT DEFAULT 'application/pdf',
        sha256_hash TEXT,
        is_locked INTEGER DEFAULT 0,
        locked_by_session_id INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
    );
    """)

    # 7. Access Requests Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS access_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_type TEXT NOT NULL CHECK(request_type IN ('normal', 'emergency')),
        patient_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        hospital_id INTEGER NOT NULL,
        reason TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('pending', 'approved', 'rejected', 'expired', 'revoked')),
        duration_minutes INTEGER DEFAULT 15,
        verification_code TEXT,
        code_expires_at DATETIME,
        verification_attempts INTEGER DEFAULT 0,
        verified_by_user_id INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
        FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
        FOREIGN KEY (hospital_id) REFERENCES hospitals(id) ON DELETE CASCADE
    );
    """)

    # 8. Access Sessions Table (Temporary Resource Allocation)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS access_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL,
        patient_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        session_token TEXT UNIQUE NOT NULL,
        access_type TEXT NOT NULL CHECK(access_type IN ('normal', 'emergency')),
        started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME NOT NULL,
        is_active INTEGER DEFAULT 1,
        revoked_at DATETIME,
        revoked_by_user_id INTEGER,
        FOREIGN KEY (request_id) REFERENCES access_requests(id) ON DELETE CASCADE,
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
        FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE
    );
    """)

    # 9. Notifications Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        data_json TEXT DEFAULT '{}',
        is_read INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # 10. Audit Logs Table (OS Security & Accountability)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        actor_id INTEGER,
        actor_name TEXT NOT NULL,
        actor_role TEXT NOT NULL,
        action TEXT NOT NULL,
        target_type TEXT,
        target_id TEXT,
        details TEXT DEFAULT '',
        ip_address TEXT DEFAULT '127.0.0.1',
        status TEXT DEFAULT 'SUCCESS',
        integrity_hash TEXT
    );
    """)

    # Create Indexes for fast lookup
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_patients_health_id ON patients(health_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_patient ON medical_records(patient_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_requests_patient ON access_requests(patient_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_sessions_token ON access_sessions(session_token);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("MediFamily OS Database initialized successfully at:", DB_PATH)
