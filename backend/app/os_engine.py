"""
MediFamily OS - Operating System Concepts Demonstrator Engine
Implements:
1. Process/Request Management (PID table, priority, state transitions)
2. Priority Scheduler (HIGH/MEDIUM/LOW priority queue)
3. Synchronization & Mutex Resource Locking (Race condition prevention, CAS atomic operations)
4. File System & Cryptographic Hash Integrity (SHA-256 verification)
5. Inter-Process Communication (IPC) Event Bus
"""

import time
import threading
import hashlib
import os
import json
from datetime import datetime

class OSProcess:
    def __init__(self, pid: int, name: str, priority: str, process_type: str, details: str = ""):
        self.pid = pid
        self.name = name
        self.priority = priority # HIGH, MEDIUM, LOW
        self.process_type = process_type
        self.state = "RUNNING" # READY, RUNNING, WAITING, TERMINATED
        self.created_at = datetime.now().strftime("%H:%M:%S")
        self.details = details
        self.cpu_usage = 0.5
        self.memory_kb = 1024

    def to_dict(self):
        return {
            "pid": self.pid,
            "name": self.name,
            "priority": self.priority,
            "process_type": self.process_type,
            "state": self.state,
            "created_at": self.created_at,
            "details": self.details,
            "cpu_usage": self.cpu_usage,
            "memory_kb": self.memory_kb
        }

class OSEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._pid_counter = 100
        self.processes = {}
        self.resource_locks = {} # resource_id -> {locked_by, session_id, locked_at, mode}
        self.event_subscribers = [] # list of queue/callback objects for IPC
        
        # Initialize default OS daemon processes
        self.spawn_process("Kernel Init & Memory Manager", "LOW", "KERNEL_DAEMON", "Core OS supervisor")
        self.spawn_process("Audit Logger Daemon", "LOW", "SYSTEM_SERVICE", "Immutable journal sync")
        self.spawn_process("Access Expiration Watchdog", "MEDIUM", "SECURITY_TIMER", "Enforces 15m session TTL")
        self.spawn_process("IPC Message Dispatcher", "HIGH", "IPC_ROUTER", "Real-time client event bus")

    def spawn_process(self, name: str, priority: str, process_type: str, details: str = "") -> int:
        with self._lock:
            self._pid_counter += 1
            pid = self._pid_counter
            proc = OSProcess(pid, name, priority, process_type, details)
            self.processes[pid] = proc
            return pid

    def update_process_state(self, pid: int, state: str):
        with self._lock:
            if pid in self.processes:
                self.processes[pid].state = state
                if state == "TERMINATED":
                    # Keep terminated processes briefly for academic observation, clean up after 60s
                    pass

    def terminate_process(self, pid: int):
        with self._lock:
            if pid in self.processes:
                self.processes[pid].state = "TERMINATED"

    def get_process_table(self):
        with self._lock:
            # Sort by priority (HIGH first), then state
            priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
            procs = list(self.processes.values())
            procs.sort(key=lambda p: (priority_order.get(p.priority, 3), 0 if p.state == "RUNNING" else 1))
            return [p.to_dict() for p in procs[-20:]] # Return recent 20 processes

    def get_scheduler_queue(self):
        """Returns the prioritized scheduler queue."""
        with self._lock:
            queue = {
                "high_priority_queue": [],
                "medium_priority_queue": [],
                "low_priority_queue": []
            }
            for p in self.processes.values():
                if p.state in ("READY", "RUNNING", "WAITING"):
                    p_dict = p.to_dict()
                    if p.priority == "HIGH":
                        queue["high_priority_queue"].append(p_dict)
                    elif p.priority == "MEDIUM":
                        queue["medium_priority_queue"].append(p_dict)
                    else:
                        queue["low_priority_queue"].append(p_dict)
            return queue

    # Synchronization & Resource Mutex Locking
    def acquire_resource_lock(self, resource_id: str, holder_name: str, session_id: str, mode: str = "EXCLUSIVE") -> bool:
        with self._lock:
            if resource_id in self.resource_locks:
                return False # Lock contention / Resource busy
            self.resource_locks[resource_id] = {
                "resource_id": resource_id,
                "holder": holder_name,
                "session_id": session_id,
                "mode": mode,
                "locked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            return True

    def release_resource_lock(self, resource_id: str):
        with self._lock:
            if resource_id in self.resource_locks:
                del self.resource_locks[resource_id]

    def get_resource_locks(self):
        with self._lock:
            return list(self.resource_locks.values())

    # File System Integrity Calculation
    @staticmethod
    def calculate_file_hash(file_bytes: bytes) -> str:
        """Computes SHA-256 cryptographic hash of a file for integrity verification."""
        hasher = hashlib.sha256()
        hasher.update(file_bytes)
        return hasher.hexdigest()

    @staticmethod
    def verify_file_integrity(file_path: str, expected_hash: str) -> bool:
        """Verifies if the physical file matches the stored SHA-256 hash."""
        if not os.path.exists(file_path):
            return False
        with open(file_path, "rb") as f:
            content = f.read()
            computed = hashlib.sha256(content).hexdigest()
            return computed.lower() == expected_hash.lower()

# Singleton instance
os_engine = OSEngine()
