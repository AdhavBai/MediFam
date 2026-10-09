"""
MediFamily OS - Patient & Family Service
Handles patient lookup, health ID cards, family relationships, and family medical overview.
"""

from backend.app.database import get_db

class PatientService:
    @staticmethod
    def get_patient_by_user_id(user_id: int):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT p.*, u.full_name, u.username, u.email, u.phone, f.family_name
            FROM patients p
            JOIN users u ON p.user_id = u.id
            JOIN families f ON p.family_id = f.id
            WHERE p.user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_patient_by_health_id(health_id: str):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT p.*, u.full_name, u.username, u.email, u.phone, f.family_name
            FROM patients p
            JOIN users u ON p.user_id = u.id
            JOIN families f ON p.family_id = f.id
            WHERE UPPER(p.health_id) = UPPER(?)
        """, (health_id.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_patient_by_id(patient_id: int):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT p.*, u.full_name, u.username, u.email, u.phone, f.family_name
            FROM patients p
            JOIN users u ON p.user_id = u.id
            JOIN families f ON p.family_id = f.id
            WHERE p.id = ?
        """, (patient_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_family_members(family_id: int):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT p.id as patient_id, p.user_id, p.health_id, p.relationship, p.blood_group,
                   p.allergies, p.existing_conditions, p.current_medications,
                   p.emergency_contact_name, p.emergency_contact_phone,
                   u.full_name, u.username, u.email, u.phone
            FROM patients p
            JOIN users u ON p.user_id = u.id
            WHERE p.family_id = ?
            ORDER BY p.id ASC
        """, (family_id,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_family_overview(family_id: int):
        """Generates comprehensive non-diagnostic family medical summary."""
        members = PatientService.get_family_members(family_id)
        db = get_db()
        cursor = db.cursor()
        
        # Count total records for family
        patient_ids = [m["patient_id"] for m in members]
        total_records = 0
        recent_activity = []
        
        if patient_ids:
            placeholders = ",".join("?" for _ in patient_ids)
            cursor.execute(f"SELECT COUNT(*) as cnt FROM medical_records WHERE patient_id IN ({placeholders})", patient_ids)
            total_records = cursor.fetchone()["cnt"]
            
            cursor.execute(f"""
                SELECT r.title, r.category, r.record_date, r.doctor_or_hospital, u.full_name as member_name
                FROM medical_records r
                JOIN patients p ON r.patient_id = p.id
                JOIN users u ON p.user_id = u.id
                WHERE r.patient_id IN ({placeholders})
                ORDER BY r.id DESC LIMIT 5
            """, patient_ids)
            recent_activity = [dict(r) for r in cursor.fetchall()]

        return {
            "family_id": family_id,
            "member_count": len(members),
            "total_records": total_records,
            "members": members,
            "recent_activity": recent_activity
        }

    @staticmethod
    def update_medical_profile(patient_id: int, blood_group: str, allergies: str, 
                               conditions: str, medications: str, contact_name: str, contact_phone: str):
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            UPDATE patients
            SET blood_group = ?, allergies = ?, existing_conditions = ?, current_medications = ?,
                emergency_contact_name = ?, emergency_contact_phone = ?
            WHERE id = ?
        """, (blood_group, allergies, conditions, medications, contact_name, contact_phone, patient_id))
        db.commit()
