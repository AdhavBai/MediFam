"""
MediFamily OS - Authentication, JWT Token & Cryptography Engine
Implements PBKDF2 password hashing, cryptographically signed JWT sessions,
RBAC enforcement, and secure OTP verification code generation.
"""

import hmac
import hashlib
import secrets
import base64
import json
import time
from datetime import datetime, timedelta

JWT_SECRET = "medifamily-os-super-secret-key-os-prototype-2026-secure-auth-991"
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24
PBKDF2_ITERATIONS = 100_000

def hash_password(password: str) -> str:
    """Hash a plaintext password using PBKDF2-HMAC-SHA256 with a random salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), PBKDF2_ITERATIONS)
    return f"{salt}:{key.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored PBKDF2 hash."""
    try:
        salt, key_hex = hashed.split(':', 1)
        key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), PBKDF2_ITERATIONS)
        return hmac.compare_digest(key.hex(), key_hex)
    except Exception:
        return False

def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def _base64url_decode(data: str) -> bytes:
    padding = '=' * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)

def create_jwt_token(payload: dict, expires_in_seconds: int = JWT_EXPIRATION_HOURS * 3600) -> str:
    """Generate an HMAC-SHA256 signed JWT token."""
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    exp_time = int(time.time()) + expires_in_seconds
    
    full_payload = {**payload, "exp": exp_time, "iat": int(time.time())}
    
    header_b64 = _base64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    payload_b64 = _base64url_encode(json.dumps(full_payload, separators=(',', ':')).encode('utf-8'))
    
    signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    signature = hmac.new(JWT_SECRET.encode('utf-8'), signing_input, hashlib.sha256).digest()
    sig_b64 = _base64url_encode(signature)
    
    return f"{header_b64}.{payload_b64}.{sig_b64}"

def decode_jwt_token(token: str) -> dict:
    """Verify and decode an HMAC-SHA256 signed JWT token."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        
        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
        expected_sig = hmac.new(JWT_SECRET.encode('utf-8'), signing_input, hashlib.sha256).digest()
        
        actual_sig = _base64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        
        payload = json.loads(_base64url_decode(payload_b64).decode('utf-8'))
        
        # Check expiration
        if 'exp' in payload and int(time.time()) > payload['exp']:
            return None # Expired
            
        return payload
    except Exception:
        return None

def generate_session_token() -> str:
    """Generate a secure cryptographic session token."""
    return f"mfsess_{secrets.token_urlsafe(32)}"

def generate_emergency_code() -> str:
    """Generate a 6-digit random emergency verification code."""
    return str(secrets.randbelow(900000) + 100000)

def generate_health_id(prefix: str, year: int = 2026) -> str:
    """Generate unique Health ID: MF-2026-XXXXX"""
    suffix = secrets.token_hex(3).upper()
    return f"MF-{year}-{prefix.upper()}{suffix}"

if __name__ == "__main__":
    pwd = "demo123"
    h = hash_password(pwd)
    print("Hashed:", h)
    print("Verified:", verify_password(pwd, h))
    token = create_jwt_token({"user_id": 1, "username": "ravi", "role": "patient"})
    print("JWT Token:", token)
    print("Decoded:", decode_jwt_token(token))
