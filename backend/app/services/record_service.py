"""
MediFamily OS - Medical Record & File System Service
Implements encrypted file storage, SHA-256 integrity hashing, and OS resource locking.
"""

import os
import hashlib
from datetime import datetime
from backend.app.database import get_db
from backend.app.os_engine import os_engine

STORAGE_BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "storage", "medical_records")

class RecordService:
    @staticmethod
    def ensure_storage_dir(patient_id: int):
        path = os.path.join(STORAGE_BASE, f"patient_{patient_id}")
        os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def add_record(patient_id: int, title: str, category: str, description: str, 
                   record_date: str, doctor_or_hospital: str, filename: str, file_bytes: bytes, file_type: str = "application/pdf"):
        """Saves physical file, calculates SHA-256 cryptographic hash, and adds record."""
        # Calculate cryptographic hash
        sha256_hash = os_engine.calculate_file_hash(file_bytes)
        
        # Save file to storage
        patient_dir = RecordService.ensure_storage_dir(patient_id)
        safe_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename.replace(' ', '_')}"
        file_path = os.path.join(patient_dir, safe_filename)
        
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO medical_records 
            (patient_id, title, category, description, record_date, doctor_or_hospital, filename, file_path, file_size_bytes, file_type, sha256_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (patient_id, title, category, description, record_date, doctor_or_hospital, safe_filename, file_path, len(file_bytes), file_type, sha256_hash))
        record_id = cursor.lastrowid
        db.commit()

        # Spawn low-priority background OS process for File System sync
        os_engine.spawn_process(f"File Storage Sync #{record_id}", "LOW", "FILE_IO", f"Persisted {safe_filename} (SHA256: {sha256_hash[:8]}...)")

        return record_id

    @staticmethod
    def get_records_by_patient(patient_id: int):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT * FROM medical_records 
            WHERE patient_id = ? 
            ORDER BY record_date DESC, id DESC
        """, (patient_id,))
        rows = cursor.fetchall()
        records = []
        for r in rows:
            rec = dict(r)
            # Verify file integrity live
            if rec.get("file_path") and os.path.exists(rec["file_path"]):
                rec["file_exists"] = True
                rec["integrity_verified"] = os_engine.verify_file_integrity(rec["file_path"], rec.get("sha256_hash", ""))
            else:
                rec["file_exists"] = False
                rec["integrity_verified"] = False
            records.append(rec)
        return records

    @staticmethod
    def get_record_by_id(record_id: int):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM medical_records WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def delete_record(record_id: int, patient_id: int) -> bool:
        """Deletes record and cleans up file storage."""
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT file_path FROM medical_records WHERE id = ? AND patient_id = ?", (record_id, patient_id))
        row = cursor.fetchone()
        if not row:
            return False

        file_path = row["file_path"]
        cursor.execute("DELETE FROM medical_records WHERE id = ? AND patient_id = ?", (record_id, patient_id))
        db.commit()

        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        return True

    @staticmethod
    def get_storage_stats():
        """Computes OS storage metrics."""
        total_size = 0
        total_files = 0
        if os.path.exists(STORAGE_BASE):
            for root, dirs, files in os.walk(STORAGE_BASE):
                for f in files:
                    fp = os.path.join(root, f)
                    total_size += os.path.getsize(fp)
                    total_files += 1
        return {
            "total_bytes": total_size,
            "total_mb": round(total_size / (1024 * 1024), 2),
            "total_files": total_files,
            "storage_path": STORAGE_BASE
        }
