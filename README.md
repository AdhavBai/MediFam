# MediFamily OS — Family Medical Records & Hospital Access System

> **Operating Systems Academic Project — Functional Prototype**  
> Demonstrating Operating System principles through a family-centric medical record and emergency break-glass access architecture.

---

## 👥 Project Team

| # | Student Name | Register Number | Role |
|---|---|---|---|
| 1 | **C.A Adhavasubash** | `RA2511026030141` | System Architect & Full-Stack Engineer |
| 2 | **MD Amman Khan** | `RA2511026020157` | OS Concepts & Cybersecurity Engineer |

**Academic Course:** Operating Systems  
**Project Type:** Operating Systems — Functional Prototype  

> **Disclaimer:** *MediFamily OS is a software platform demonstrating Operating System concepts (process management, synchronization, resource allocation, access control, audit logging, and IPC). It is an academic prototype and is not intended for real clinical diagnosis or production healthcare deployment.*

---

## 🎯 System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        MEDIFAMILY OS WEB SERVER                        │
│             (REST API Router + Real-Time SSE/WebSocket Bus)            │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
       ┌────────────────────────────┼────────────────────────────┐
       ▼                            ▼                            ▼
 Patient / Family View       Doctor / Hospital Portal      Admin & OS Dashboard
  (Web & Mobile Phone)       (Clinical Workspace & ER)     (Telemetry & Audit)
       │                            │                            │
       └────────────────────────────┼────────────────────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │       DATABASE (SQLite)       │
                    │   Schema, Indices & Triggers  │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │     SECURE STORAGE VAULT      │
                    │  /storage/medical_records/    │
                    │  (SHA-256 Cryptographic Hash) │
                    └───────────────────────────────┘
```

---

## 🧠 Operating System Concepts Demonstrated

| OS Concept | How MediFamily OS Implements It |
|---|---|
| **Process & PCB Management** | Each access request, file I/O task, and daemon creates a tracked Process Control Block with PID (e.g. PID 101), Process State (`RUNNING`, `WAITING`, `READY`, `TERMINATED`), and CPU/Memory allocation. |
| **Priority Scheduling & Preemption** | Multi-level queue scheduler with 3 priorities: `HIGH` (Emergency Break-Glass — Preempts lower queues), `MEDIUM` (Normal Access Consultations), `LOW` (Background File I/O & Audit Sync). |
| **Synchronization & Mutex Locking** | Resource mutex locks on `/storage/medical_records/` preventing race conditions during concurrent file modifications and doctor access sessions. |
| **Atomic Concurrency (CAS)** | First-Valid-Approval-Wins on Emergency Access: when multiple family members receive the emergency OTP, only the first approval succeeds atomically; subsequent attempts receive `"Already Approved"`. |
| **Temporary Resource Allocation** | Capability-based temporary session tokens with exact 15-minute Time-To-Live (TTL), enforced server-side with automatic session expiration watchdogs. |
| **File System & Integrity** | Structured filesystem in `/storage/medical_records/` with real-time SHA-256 cryptographic hashing to verify data integrity against tampering. |
| **Inter-Process Communication (IPC)** | Real-time Server-Sent Events (SSE) and WebSocket message bus allowing asynchronous event broadcast between independent browser processes. |
| **Role-Based Access Control (RBAC)** | Strict privilege separation between `PATIENT`, `DOCTOR`, and `ADMIN` enforced via JWT signature verification. |
| **Immutable Audit Logging** | Tamper-evident audit trail with cryptographic hash chaining recording every sensitive operation. |

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10+ (Standard library — zero external C-dependency hurdles)
- Modern web browser (Chrome, Edge, Firefox, Safari, Android Chrome)

### 2. Run the Application
From the project root directory:

```bash
# Initialize and seed database
python -m backend.app.seed

# Start the full-stack server & launch browser
python run.py
```

Server will start on:
- **Local Browser:** `http://localhost:8000`
- **LAN / Mobile Phone:** `http://<YOUR_PC_IP>:8000`
- **API Documentation:** `http://localhost:8000/api/docs`

---

## 🔑 Demo Accounts

Use the **One-Click Demo Switcher** on the login page or sign in manually:

| Role | Username | Password | Health ID | Key Details |
|---|---|---|---|---|
| **Patient (Father)** | `ravi` | `demo123` | `MF-2026-RAVI01` | Blood: O+, Allergy: Penicillin, Asthma |
| **Patient (Mother)** | `priya` | `demo123` | `MF-2026-PRIYA1` | Blood: A+, Authorized Emergency Verifier |
| **Patient (Son)** | `arjun` | `demo123` | `MF-2026-ARJUN1` | Blood: O+, Allergy: Peanuts |
| **Doctor / ER** | `arun` | `demo123` | N/A | Apollo Demo Hospital (Trauma Specialist) |
| **Administrator** | `admin` | `admin123` | N/A | Full telemetry, logs, and system stats |

---

## 🎬 College Presentation & Evaluation Scripts

### Demo Scenario 1 — Normal Doctor Consultation Access (7-Step Workflow)
1. **Window 1 (Doctor):** Log in as `arun` (`demo123`). Search patient `MF-2026-RAVI01` and click `[ REQUEST ACCESS ]`.
2. **Window 2 (Patient):** Log in as `ravi` (`demo123`) on a second browser window or phone.
3. Notice the **instant real-time alert banner** appearing on Ravi's screen with Dr. Arun's details.
4. Click **`[ APPROVE ACCESS ]`**.
5. Doctor's screen in Window 1 **instantly unlocks** with a 15-minute countdown clock and patient clinical chart.
6. In Window 2 (Patient), click **`[ REVOKE ACCESS ]`**.
7. Doctor's screen in Window 1 **immediately locks** with an *"Access Revoked"* security notice without refreshing!

---

### Demo Scenario 2 — Emergency "Break-Glass" Accident Workflow (Atomic Concurrency)
1. **Window 1 (Doctor / ER):** Log in as `arun`. Search `MF-2026-RAVI01` and click `[ 🚨 EMERGENCY ACCESS ]`. Reason: `"Highway Collision - Trauma Shock"`.
2. **Window 2 (Mother - Priya):** Log in as `priya` (`demo123`).
3. **Window 3 (Son - Arjun):** Log in as `arjun` (`demo123`).
4. Both family members instantly receive the **Audible Siren Alert** and 6-digit verification code (e.g. `482913`).
5. In Window 2, Priya enters the code and clicks **`[ VERIFY & APPROVE EMERGENCY ]`**.
6. Doctor's screen immediately unlocks the **Emergency Medical Summary** (Severe Penicillin Allergy Alert + Blood Group O+).
7. In Window 3, Arjun attempts to enter the code: backend responds with **`"Emergency request already approved by another family member"`** (demonstrating atomic CAS / race condition prevention).

---

## 📱 Local Network (Mobile Phone / Android) Setup

To demonstrate on a physical smartphone over the same Wi-Fi:

1. Find your PC's IP address:
   - Windows: `ipconfig` (look for IPv4 Address, e.g. `192.168.1.15`)
2. Start MediFamily OS:
   ```bash
   python run.py --host 0.0.0.0 --port 8000
   ```
3. Open your mobile browser (Chrome/Safari) and navigate to:
   ```
   http://192.168.1.15:8000
   ```
4. Log in as `ravi` on your phone and `arun` on your PC to demonstrate cross-device real-time communication!

---

## 🧪 Automated Testing

Run the test suite verifying all 6 core subsystems:

```bash
python run_tests.py
```

**Verified Test Cases:**
- `test_01_password_and_jwt_auth`: PBKDF2 hashing, salt generation, HMAC-SHA256 JWT validation.
- `test_02_patient_lookup_and_family`: Unique Health ID resolution, family hierarchy traversal.
- `test_03_medical_record_sha256_integrity`: Cryptographic file integrity calculation & verification.
- `test_04_normal_access_workflow`: Full 7-step request -> consent -> session -> revocation lifecycle.
- `test_05_emergency_break_glass_first_approval_wins`: Atomic concurrency and race condition prevention.
- `test_06_os_concepts_engine`: PCB process table, priority queue scheduler, mutex resource locks.

---

## 📂 Project Structure

```
medifamily-os/
├── backend/
│   ├── app/
│   │   ├── auth.py              # PBKDF2, JWT tokens, RBAC, OTP generation
│   │   ├── database.py          # SQLite connection, schema, triggers, indices
│   │   ├── os_engine.py         # OS Process manager, Priority Scheduler, Mutex Locks
│   │   ├── seed.py              # Demo accounts & medical records seeder
│   │   ├── server.py            # High-performance HTTP server, REST APIs & SSE stream
│   │   └── services/
│   │       ├── access_service.py       # Temporary access sessions & revocation
│   │       ├── audit_service.py        # SHA-256 hash-chained audit journal
│   │       ├── emergency_service.py    # Break-Glass override & atomic concurrency
│   │       ├── notification_service.py # Real-time event bus & notifications
│   │       ├── patient_service.py      # Health IDs & family overview
│   │       └── record_service.py       # Encrypted storage & file integrity
├── frontend/
│   ├── css/
│   │   └── styles.css           # Healthcare theme, sirens, holographic health cards
│   ├── js/
│   │   ├── api.js               # REST client & session management
│   │   ├── realtime.js          # Real-time SSE listener & Web Audio chimes
│   │   └── app.js               # SPA router & OS concept visualizers
│   └── index.html               # Responsive web & mobile UI shell
├── storage/
│   └── medical_records/         # File storage with SHA-256 verification
├── tests/
│   └── test_suite.py            # Comprehensive unit and integration test suite
├── run.py                       # One-click launcher
├── run_tests.py                 # Test runner script
└── README.md                    # Project documentation
```

---

## 📜 Academic Evaluation Summary

- **Course:** Operating Systems
- **Project Title:** MediFamily OS — Family-Centric Medical Records & Emergency Access System
- **Authors:** C.A Adhavasubash (`RA2511026030141`) & MD Amman Khan (`RA2511026020157`)
- **Footer Notice:** `MediFamily OS — Academic Prototype | Not intended for real clinical use`
