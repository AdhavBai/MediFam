/**
 * MediFamily OS - Main Application Controller & UI State Engine
 * Manages views, role routing, medical records, access workflows, and OS concept visualizers.
 */

const App = {
    currentUser: null,
    currentRole: null,
    activeTab: 'view-patient',
    sessionCountdownTimer: null,
    activeDoctorSession: null,
    osRefreshInterval: null,

    async init() {
        console.log("Initializing MediFamily OS Web Application...");
        
        // Setup real-time event listeners
        this.setupRealtimeHandlers();

        // Check if token already exists
        const token = API.getToken();
        if (token) {
            try {
                const res = await API.getMe();
                if (res.success && res.user) {
                    this.setCurrentUser(res.user);
                    return;
                }
            } catch (e) {
                console.warn("Session restore failed, returning to login screen:", e);
                API.setToken(null);
            }
        }

        this.showLogin();
    },

    setCurrentUser(user) {
        this.currentUser = user;
        this.currentRole = user.role;
        API.setCurrentUser(user);

        // Update Nav UI
        document.getElementById('nav-user-name').innerText = user.full_name || user.username;
        document.getElementById('nav-user-role').innerText = user.role.toUpperCase();
        document.getElementById('logged-in-nav').classList.remove('hidden');
        document.getElementById('login-modal').classList.add('hidden');

        // Connect Realtime SSE
        realtime.init();

        // Route to primary view based on role
        if (user.role === 'patient') {
            this.switchTab('view-patient');
            this.loadPatientDashboard();
        } else if (user.role === 'doctor') {
            this.switchTab('view-doctor');
            this.loadDoctorPortal();
        } else if (user.role === 'admin') {
            this.switchTab('view-admin');
            this.loadAdminDashboard();
        }

        this.loadNotifications();
        if (window.lucide) lucide.createIcons();
    },

    showLogin() {
        this.currentUser = null;
        this.currentRole = null;
        API.setToken(null);
        API.setSessionToken(null);
        document.getElementById('logged-in-nav').classList.add('hidden');
        document.getElementById('login-modal').classList.remove('hidden');
        this.hideAllViews();
        if (this.osRefreshInterval) clearInterval(this.osRefreshInterval);
    },

    hideAllViews() {
        ['view-patient', 'view-doctor', 'view-admin', 'view-os-concepts', 'view-family-overview', 'view-audit'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.add('hidden');
        });
    },

    switchTab(tabId) {
        this.activeTab = tabId;
        this.hideAllViews();
        const target = document.getElementById(tabId);
        if (target) target.classList.remove('hidden');

        // Update nav active styles
        document.querySelectorAll('.nav-link').forEach(btn => {
            if (btn.dataset.target === tabId) {
                btn.classList.add('bg-slate-800', 'text-cyan-400');
                btn.classList.remove('text-slate-300');
            } else {
                btn.classList.remove('bg-slate-800', 'text-cyan-400');
                btn.classList.add('text-slate-300');
            }
        });

        // Tab specific refresh
        if (tabId === 'view-patient') this.loadPatientDashboard();
        if (tabId === 'view-doctor') this.loadDoctorPortal();
        if (tabId === 'view-admin') this.loadAdminDashboard();
        if (tabId === 'view-os-concepts') this.loadOSConcepts();
        if (tabId === 'view-family-overview') this.loadFamilyOverview();
        if (tabId === 'view-audit') this.loadAuditLogs();

        if (window.lucide) lucide.createIcons();
    },

    // ------------------ AUTH METHODS ------------------
    async handleLogin(username, password) {
        try {
            const res = await API.login(username, password);
            if (res.success && res.token) {
                API.setToken(res.token);
                realtime.showToast('Login Successful', `Welcome back, ${res.user.full_name}`, 'success');
                this.setCurrentUser(res.user);
            }
        } catch (err) {
            realtime.showToast('Authentication Error', err.message, 'warning');
        }
    },

    quickLogin(username) {
        const passwords = {
            ravi: 'demo123',
            priya: 'demo123',
            arjun: 'demo123',
            arun: 'demo123',
            admin: 'admin123'
        };
        const pwd = passwords[username] || 'demo123';
        this.handleLogin(username, pwd);
    },

    logout() {
        API.setToken(null);
        API.setSessionToken(null);
        API.setCurrentUser(null);
        this.showLogin();
        realtime.showToast('Logged Out', 'You have been securely signed out.', 'info');
    },

    // ------------------ REAL-TIME DISPATCH HANDLERS ------------------
    setupRealtimeHandlers() {
        // When patient receives an access request
        realtime.on('notification', (data) => {
            this.loadNotifications();
            if (this.currentRole === 'patient') {
                this.loadPatientDashboard();
            }
            // If it's an emergency notification, pop up the emergency verification dialog
            if (data.type === 'emergency_request') {
                this.showEmergencyVerifyModal(data.data);
            }
        });

        // When doctor gets approval
        realtime.on('access_approved', (data) => {
            if (this.currentRole === 'doctor') {
                API.setSessionToken(data.session_token);
                this.activeDoctorSession = data;
                this.renderDoctorClinicalChart(data);
            }
        });

        // When doctor gets emergency approval
        realtime.on('emergency_approved', (data) => {
            if (this.currentRole === 'doctor') {
                API.setSessionToken(data.session_token);
                this.activeDoctorSession = data;
                this.renderDoctorClinicalChart(data, true);
            }
        });

        // When patient revokes access
        realtime.on('access_revoked', (data) => {
            if (this.currentRole === 'doctor') {
                API.setSessionToken(null);
                this.activeDoctorSession = null;
                this.lockDoctorScreen("Access to patient records has been revoked by the patient.");
            }
            if (this.currentRole === 'patient') {
                this.loadPatientDashboard();
            }
        });

        // When demo data is reset
        realtime.on('system_reset', () => {
            if (this.currentUser) {
                API.getMe().then(res => {
                    if (res.success) this.setCurrentUser(res.user);
                }).catch(() => this.showLogin());
            }
        });
    },

    // ------------------ PATIENT DASHBOARD ------------------
    async loadPatientDashboard() {
        if (!this.currentUser || this.currentUser.role !== 'patient') return;
        const patient = this.currentUser.patient || this.currentUser.patient_profile;
        if (!patient) return;

        // Render Greetings & Stats
        const greeting = document.getElementById('patient-greeting');
        if (greeting) greeting.innerText = `Good ${this.getTimeOfDay()}, ${this.currentUser.full_name.split(' ')[0]}`;

        document.getElementById('patient-uhid-display').innerText = patient.health_id;
        document.getElementById('patient-blood-group').innerText = patient.blood_group || 'O+';
        document.getElementById('patient-allergies').innerText = patient.allergies || 'None';
        document.getElementById('patient-conditions').innerText = patient.existing_conditions || 'None';
        document.getElementById('patient-medications').innerText = patient.current_medications || 'None';
        document.getElementById('patient-emergency-contact').innerText = `${patient.emergency_contact_name || 'N/A'} (${patient.emergency_contact_phone || ''})`;

        // Render Digital QR Code for Health ID
        this.renderQRCode('patient-qr-code', patient.health_id);

        // Fetch Medical Records
        try {
            const recordsRes = await API.getPatientRecords(patient.id);
            if (recordsRes.success) {
                document.getElementById('patient-records-count').innerText = recordsRes.records.length;
                this.renderMedicalRecordsGrid(recordsRes.records, 'patient-records-container', true);
            }
        } catch (e) {
            console.error("Failed to fetch patient records:", e);
        }

        // Fetch Active Sessions
        try {
            const sessRes = await API.getActiveSessions(patient.id);
            if (sessRes.success) {
                document.getElementById('patient-active-sessions-count').innerText = sessRes.active_sessions.length;
                this.renderPatientActiveSessions(sessRes.active_sessions);
            }
        } catch (e) {
            console.error("Failed to fetch active sessions:", e);
        }

        // Check for pending access requests from notifications
        this.checkPendingAccessRequests();

        if (window.lucide) lucide.createIcons();
    },

    renderQRCode(containerId, text) {
        const el = document.getElementById(containerId);
        if (!el) return;
        el.innerHTML = '';
        
        // Clean high-contrast SVG QR Code generation
        if (typeof QRCode !== 'undefined') {
            new QRCode(el, {
                text: text,
                width: 130,
                height: 130,
                colorDark : "#0284c7",
                colorLight : "#ffffff",
                correctLevel : QRCode.CorrectLevel.H
            });
        } else {
            // Fallback SVG QR placeholder
            el.innerHTML = `<div class="w-32 h-32 bg-white rounded-lg p-2 flex flex-col items-center justify-center border border-cyan-400">
                <i data-lucide="qr-code" class="w-16 h-16 text-slate-800"></i>
                <span class="text-[10px] font-mono text-slate-800 font-bold mt-1">${text}</span>
            </div>`;
        }
    },

    renderMedicalRecordsGrid(records, containerId, allowDelete = false) {
        const container = document.getElementById(containerId);
        if (!container) return;

        if (!records || records.length === 0) {
            container.innerHTML = `
                <div class="col-span-full p-8 text-center bg-slate-800/40 rounded-xl border border-slate-700/60">
                    <i data-lucide="folder-open" class="w-12 h-12 text-slate-500 mx-auto mb-2"></i>
                    <p class="text-slate-400 text-sm">No medical records uploaded yet.</p>
                </div>
            `;
            return;
        }

        const categoryIcons = {
            'Prescription': 'pill',
            'Blood Report': 'flask-conical',
            'X-Ray': 'scan-line',
            'Scan': 'scan',
            'Discharge Summary': 'file-text',
            'Lab Report': 'activity',
            'Medical Certificate': 'award'
        };

        container.innerHTML = records.map(r => {
            const icon = categoryIcons[r.category] || 'file';
            const sizeKb = Math.round((r.file_size_bytes || 1024) / 1024);
            const integrityBadge = r.integrity_verified 
                ? `<span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-950/80 text-emerald-400 border border-emerald-700/80"><i data-lucide="shield-check" class="w-3 h-3 mr-1"></i> SHA-256 VERIFIED</span>`
                : `<span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-950/80 text-amber-400 border border-amber-700/80"><i data-lucide="shield-alert" class="w-3 h-3 mr-1"></i> PENDING VERIFY</span>`;

            return `
                <div class="glass-panel p-5 rounded-xl border border-slate-700/80 hover:border-cyan-500/50 transition-all flex flex-col justify-between">
                    <div>
                        <div class="flex items-start justify-between mb-3">
                            <div class="w-10 h-10 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 flex items-center justify-center">
                                <i data-lucide="${icon}" class="w-5 h-5"></i>
                            </div>
                            ${integrityBadge}
                        </div>
                        <h4 class="text-sm font-bold text-white mb-1 line-clamp-1">${r.title}</h4>
                        <div class="text-xs text-slate-400 mb-2 flex items-center space-x-2">
                            <span><i data-lucide="calendar" class="w-3.5 h-3.5 inline mr-1 text-slate-500"></i>${r.record_date}</span>
                            <span>•</span>
                            <span class="text-cyan-400 font-medium">${r.category}</span>
                        </div>
                        <p class="text-xs text-slate-300 leading-relaxed mb-4 line-clamp-2">${r.description || 'No description provided.'}</p>
                    </div>

                    <div class="pt-3 border-t border-slate-800/80 flex items-center justify-between">
                        <div class="text-[11px] text-slate-500 font-mono">
                            ${r.doctor_or_hospital || 'Apollo Diagnostics'} • ${sizeKb} KB
                        </div>
                        <div class="flex items-center space-x-2">
                            <button onclick="App.viewRecordDetail(${r.id})" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-cyan-400 text-xs font-semibold rounded border border-slate-700 transition">
                                View
                            </button>
                            <a href="/storage/medical_records/patient_${r.patient_id}/${r.filename}" target="_blank" download class="px-2.5 py-1 bg-cyan-600/20 hover:bg-cyan-600/40 text-cyan-300 text-xs font-semibold rounded border border-cyan-500/30 transition">
                                Download
                            </a>
                            ${allowDelete ? `
                            <button onclick="App.deleteRecord(${r.id})" class="p-1 hover:bg-red-950/50 text-slate-500 hover:text-red-400 rounded transition" title="Delete Record">
                                <i data-lucide="trash-2" class="w-4 h-4"></i>
                            </button>` : ''}
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        if (window.lucide) lucide.createIcons();
    },

    renderPatientActiveSessions(sessions) {
        const container = document.getElementById('patient-active-sessions-list');
        if (!container) return;

        if (!sessions || sessions.length === 0) {
            container.innerHTML = `<p class="text-xs text-slate-500 italic p-3">No hospitals or doctors currently have active access to your records.</p>`;
            return;
        }

        container.innerHTML = sessions.map(s => {
            const expDate = new Date(s.expires_at.replace(' ', 'T'));
            const isEmergency = s.access_type === 'emergency';

            return `
                <div class="p-3.5 rounded-xl ${isEmergency ? 'bg-red-950/30 border border-red-800/60 emergency-glow' : 'bg-slate-800/70 border border-slate-700/80'} flex items-center justify-between mb-2">
                    <div class="flex items-center space-x-3">
                        <div class="w-9 h-9 rounded-lg ${isEmergency ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20'} flex items-center justify-center">
                            <i data-lucide="${isEmergency ? 'alert-triangle' : 'shield-check'}" class="w-5 h-5"></i>
                        </div>
                        <div>
                            <div class="flex items-center space-x-2">
                                <h5 class="text-xs font-bold text-white">${s.hospital_name}</h5>
                                <span class="text-[10px] px-2 py-0.5 rounded font-semibold ${isEmergency ? 'bg-red-500/20 text-red-300' : 'bg-cyan-500/20 text-cyan-300'}">${s.access_type.toUpperCase()}</span>
                            </div>
                            <p class="text-[11px] text-slate-400">${s.doctor_name} (${s.specialty || 'General'}) • Expires at ${expDate.toLocaleTimeString()}</p>
                        </div>
                    </div>

                    <button onclick="App.revokeSession(${s.id})" class="px-3 py-1.5 bg-red-600/80 hover:bg-red-600 text-white text-xs font-bold rounded-lg shadow transition flex items-center space-x-1">
                        <i data-lucide="lock" class="w-3.5 h-3.5"></i>
                        <span>REVOKE ACCESS</span>
                    </button>
                </div>
            `;
        }).join('');

        if (window.lucide) lucide.createIcons();
    },

    async checkPendingAccessRequests() {
        try {
            const notifsRes = await API.getNotifications();
            if (!notifsRes.success) return;

            const pending = notifsRes.notifications.find(n => n.type === 'normal_request' && !n.is_read);
            const banner = document.getElementById('pending-access-banner');
            if (!banner) return;

            if (pending && pending.data) {
                banner.classList.remove('hidden');
                document.getElementById('pending-req-doctor').innerText = `${pending.data.hospital_name} (${pending.data.doctor_name})`;
                document.getElementById('pending-req-reason').innerText = `"${pending.data.reason || 'Clinical Consultation'}"`;
                document.getElementById('pending-req-duration').innerText = `${pending.data.duration_minutes || 15} minutes`;
                
                document.getElementById('btn-approve-req').onclick = async () => {
                    try {
                        const res = await API.approveAccess(pending.data.request_id);
                        if (res.success) {
                            await API.markNotificationRead(pending.id);
                            banner.classList.add('hidden');
                            realtime.showToast('Access Approved', 'Doctor has been granted temporary access.', 'success');
                            this.loadPatientDashboard();
                        }
                    } catch (e) {
                        realtime.showToast('Error', e.message, 'warning');
                    }
                };

                document.getElementById('btn-reject-req').onclick = async () => {
                    try {
                        const res = await API.rejectAccess(pending.data.request_id);
                        if (res.success) {
                            await API.markNotificationRead(pending.id);
                            banner.classList.add('hidden');
                            realtime.showToast('Access Declined', 'Access request has been rejected.', 'info');
                            this.loadPatientDashboard();
                        }
                    } catch (e) {
                        realtime.showToast('Error', e.message, 'warning');
                    }
                };
            } else {
                banner.classList.add('hidden');
            }
        } catch (e) {}
    },

    async revokeSession(sessionId) {
        try {
            const res = await API.revokeSession(sessionId);
            if (res.success) {
                realtime.showToast('Access Revoked', 'Doctor access has been terminated immediately.', 'warning');
                this.loadPatientDashboard();
            }
        } catch (e) {
            realtime.showToast('Error', e.message, 'warning');
        }
    },

    async deleteRecord(recordId) {
        if (!confirm("Are you sure you want to permanently delete this medical record?")) return;
        try {
            const res = await API.deleteRecord(recordId);
            if (res.success) {
                realtime.showToast('Record Deleted', 'Medical record and encrypted file removed.', 'info');
                this.loadPatientDashboard();
            }
        } catch (e) {
            realtime.showToast('Error', e.message, 'warning');
        }
    },

    // ------------------ DOCTOR / HOSPITAL PORTAL ------------------
    async loadDoctorPortal() {
        if (!this.currentUser || this.currentUser.role !== 'doctor') return;
        const doc = this.currentUser.doctor || this.currentUser.doctor_profile;
        if (!doc) return;

        document.getElementById('doctor-name-display').innerText = doc.doctor_name;
        document.getElementById('doctor-hospital-display').innerText = `${doc.hospital_name || 'Apollo Demo Hospital'} • ${doc.specialty || 'Trauma Care'}`;

        // If session token already active, load patient chart
        const sessToken = API.getSessionToken();
        if (sessToken && this.activeDoctorSession) {
            this.renderDoctorClinicalChart(this.activeDoctorSession);
        } else {
            document.getElementById('doctor-patient-chart').classList.add('hidden');
            document.getElementById('doctor-search-box').classList.remove('hidden');
        }

        if (window.lucide) lucide.createIcons();
    },

    async searchPatient(healthId) {
        if (!healthId) healthId = document.getElementById('search-health-id-input').value.trim();
        if (!healthId) {
            realtime.showToast('Input Required', 'Please enter a valid Unique Health ID (e.g. MF-2026-RAVI01)', 'info');
            return;
        }

        try {
            const res = await API.getPatientByHealthId(healthId);
            if (res.success && res.patient) {
                const pat = res.patient;
                document.getElementById('found-patient-card').classList.remove('hidden');
                document.getElementById('found-patient-name').innerText = pat.full_name;
                document.getElementById('found-patient-hid').innerText = pat.health_id;
                document.getElementById('found-patient-bg').innerText = pat.blood_group;
                document.getElementById('found-patient-age').innerText = `${pat.gender || 'Male'} • ${pat.relationship || 'Father'}`;

                // Wire up Action Buttons
                document.getElementById('btn-doc-request-normal').onclick = () => this.showNormalRequestModal(pat);
                document.getElementById('btn-doc-request-emergency').onclick = () => this.showEmergencyRequestModal(pat);
            }
        } catch (e) {
            document.getElementById('found-patient-card').classList.add('hidden');
            realtime.showToast('Patient Not Found', e.message, 'warning');
        }
    },

    showNormalRequestModal(patient) {
        document.getElementById('req-modal-hid').innerText = patient.health_id;
        document.getElementById('req-modal-patient-name').innerText = patient.full_name;
        document.getElementById('normal-request-modal').classList.remove('hidden');

        document.getElementById('btn-submit-normal-req').onclick = async () => {
            const reason = document.getElementById('req-modal-reason').value.trim() || "Clinical Consultation & Health Assessment";
            const duration = parseInt(document.getElementById('req-modal-duration').value || "15");

            try {
                const res = await API.requestAccess(patient.health_id, reason, duration);
                if (res.success) {
                    document.getElementById('normal-request-modal').classList.add('hidden');
                    realtime.showToast('Request Sent', 'Waiting for patient approval notification...', 'info');
                }
            } catch (e) {
                realtime.showToast('Error', e.message, 'warning');
            }
        };
    },

    showEmergencyRequestModal(patient) {
        document.getElementById('em-modal-hid').innerText = patient.health_id;
        document.getElementById('em-modal-patient-name').innerText = patient.full_name;
        document.getElementById('emergency-request-modal').classList.remove('hidden');

        document.getElementById('btn-submit-emergency-req').onclick = async () => {
            const reason = document.getElementById('em-modal-reason').value.trim() || "High-Speed Highway Collision - Acute Hemorrhage & Hypoxia";
            
            try {
                const res = await API.requestEmergency(patient.health_id, reason);
                if (res.success) {
                    document.getElementById('emergency-request-modal').classList.add('hidden');
                    realtime.showToast('🚨 Break-Glass Initiated', `Verification code (${res.demo_verification_code}) broadcasted to family members!`, 'emergency');
                }
            } catch (e) {
                realtime.showToast('Error', e.message, 'warning');
            }
        };
    },

    async renderDoctorClinicalChart(sessionData, isEmergency = false) {
        document.getElementById('doctor-search-box').classList.add('hidden');
        const chart = document.getElementById('doctor-patient-chart');
        chart.classList.remove('hidden');

        document.getElementById('chart-patient-name').innerText = sessionData.patient_name;
        document.getElementById('chart-patient-hid').innerText = sessionData.health_id;
        document.getElementById('chart-session-badge').innerText = isEmergency ? '🚨 EMERGENCY BREAK-GLASS' : '🔐 AUTHORIZED CONSULTATION';
        document.getElementById('chart-session-badge').className = `text-xs px-2.5 py-1 rounded font-bold ${isEmergency ? 'bg-red-500/20 text-red-300 border border-red-500/40' : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'}`;

        // Start countdown timer
        this.startSessionTimer(sessionData.expires_at);

        // Fetch Emergency Summary
        try {
            const sumRes = await API.getEmergencySummary(sessionData.health_id);
            if (sumRes.success && sumRes.emergency_summary) {
                const s = sumRes.emergency_summary;
                document.getElementById('chart-blood-group').innerText = s.blood_group;
                document.getElementById('chart-allergies').innerText = s.allergies || 'None';
                document.getElementById('chart-conditions').innerText = s.existing_conditions || 'None';
                document.getElementById('chart-medications').innerText = s.current_medications || 'None';
                document.getElementById('chart-emergency-contact').innerText = `${s.emergency_contact_name} (${s.emergency_contact_phone})`;

                // Highlight severe allergy alert
                if (s.allergies && s.allergies.toLowerCase().includes('penicillin')) {
                    document.getElementById('allergy-alert-banner').classList.remove('hidden');
                    document.getElementById('allergy-alert-text').innerText = `⚠️ CRITICAL ALLERGY: Patient is highly allergic to ${s.allergies}. Do NOT administer Beta-Lactam antibiotics.`;
                } else {
                    document.getElementById('allergy-alert-banner').classList.add('hidden');
                }
            }
        } catch (e) {}

        // Fetch Medical Records
        try {
            const recRes = await API.getPatientRecords(sessionData.patient_id);
            if (recRes.success) {
                this.renderMedicalRecordsGrid(recRes.records, 'chart-records-container', false);
            }
        } catch (e) {
            console.error("Failed to load records in chart:", e);
        }

        if (window.lucide) lucide.createIcons();
    },

    startSessionTimer(expiresAtStr) {
        if (this.sessionCountdownTimer) clearInterval(this.sessionCountdownTimer);
        const expTime = new Date(expiresAtStr.replace(' ', 'T')).getTime();

        const updateClock = () => {
            const now = new Date().getTime();
            const diff = expTime - now;

            if (diff <= 0) {
                clearInterval(this.sessionCountdownTimer);
                document.getElementById('session-countdown-display').innerText = '00:00 (EXPIRED)';
                this.lockDoctorScreen("Access session has reached its time limit and expired.");
                return;
            }

            const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
            const secs = Math.floor((diff % (1000 * 60)) / 1000);
            document.getElementById('session-countdown-display').innerText = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')} remaining`;
        };

        updateClock();
        this.sessionCountdownTimer = setInterval(updateClock, 1000);
    },

    lockDoctorScreen(reason) {
        if (this.sessionCountdownTimer) clearInterval(this.sessionCountdownTimer);
        const chart = document.getElementById('doctor-patient-chart');
        if (chart) chart.classList.add('hidden');
        document.getElementById('doctor-search-box').classList.remove('hidden');
        realtime.showToast('Access Locked', reason, 'warning');
    },

    // ------------------ EMERGENCY VERIFICATION MODAL ------------------
    showEmergencyVerifyModal(data) {
        const modal = document.getElementById('emergency-verify-modal');
        if (!modal) return;

        modal.classList.remove('hidden');
        document.getElementById('em-verify-patient-name').innerText = data.patient_name;
        document.getElementById('em-verify-hospital').innerText = `${data.hospital_name} (${data.doctor_name})`;
        document.getElementById('em-verify-reason').innerText = `"${data.reason}"`;
        
        const codeInput = document.getElementById('em-verify-code-input');
        codeInput.value = data.verification_code || '';
        codeInput.focus();

        document.getElementById('btn-submit-em-verify').onclick = async () => {
            const entered = codeInput.value.trim();
            if (!entered) {
                realtime.showToast('Code Required', 'Please enter the 6-digit emergency verification code', 'warning');
                return;
            }

            try {
                const res = await API.approveEmergency(data.request_id, entered);
                if (res.success) {
                    modal.classList.add('hidden');
                    realtime.showToast('✓ Emergency Access Verified', 'ER Trauma team has been granted immediate 15-minute access.', 'emergency');
                    this.loadPatientDashboard();
                }
            } catch (e) {
                realtime.showToast('Verification Failed', e.message, 'warning');
            }
        };
    },

    // ------------------ OS CONCEPTS ENGINE DASHBOARD ------------------
    async loadOSConcepts() {
        const fetchOS = async () => {
            try {
                const res = await API.getOSConcepts();
                if (res.success && res.os_data) {
                    this.renderOSProcessTable(res.os_data.processes);
                    this.renderOSSchedulerQueue(res.os_data.scheduler_queue);
                    this.renderOSResourceLocks(res.os_data.resource_locks);
                    this.renderOSStorageStats(res.os_data.storage_stats);
                }
            } catch (e) {
                console.error("Failed to load OS concepts:", e);
            }
        };

        fetchOS();
        if (this.osRefreshInterval) clearInterval(this.osRefreshInterval);
        this.osRefreshInterval = setInterval(fetchOS, 2500); // 2.5s auto-refresh
    },

    renderOSProcessTable(processes) {
        const tbody = document.getElementById('os-process-table-body');
        if (!tbody) return;

        tbody.innerHTML = processes.map(p => {
            let priorityBadge = `badge-${p.priority.toLowerCase()}`;
            let stateColor = p.state === 'RUNNING' ? 'text-emerald-400 font-bold' : (p.state === 'WAITING' ? 'text-amber-400' : 'text-slate-400');

            return `
                <tr class="border-b border-slate-800 hover:bg-slate-800/40 transition">
                    <td class="py-2.5 px-3 font-mono text-cyan-400 font-bold">${p.pid}</td>
                    <td class="py-2.5 px-3 font-semibold text-white">${p.name}</td>
                    <td class="py-2.5 px-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold ${priorityBadge}">${p.priority}</span></td>
                    <td class="py-2.5 px-3 ${stateColor}">${p.state}</td>
                    <td class="py-2.5 px-3 font-mono text-xs text-slate-400">${p.cpu_usage}% / ${p.memory_kb} KB</td>
                    <td class="py-2.5 px-3 text-xs text-slate-400">${p.details}</td>
                </tr>
            `;
        }).join('');
    },

    renderOSSchedulerQueue(queue) {
        const renderList = (items, colorClass) => {
            if (!items || items.length === 0) return `<li class="text-xs text-slate-500 italic">Queue Empty (Idle)</li>`;
            return items.map(p => `
                <li class="p-2 bg-slate-900/60 rounded border border-slate-800 flex justify-between items-center text-xs">
                    <span class="font-bold text-white"><span class="font-mono text-cyan-400">#${p.pid}</span> ${p.name}</span>
                    <span class="text-[10px] font-mono ${colorClass}">${p.state}</span>
                </li>
            `).join('');
        };

        const highEl = document.getElementById('scheduler-high-queue');
        const medEl = document.getElementById('scheduler-medium-queue');
        const lowEl = document.getElementById('scheduler-low-queue');

        if (highEl) highEl.innerHTML = renderList(queue.high_priority_queue, 'text-red-400');
        if (medEl) medEl.innerHTML = renderList(queue.medium_priority_queue, 'text-amber-400');
        if (lowEl) lowEl.innerHTML = renderList(queue.low_priority_queue, 'text-emerald-400');
    },

    renderOSResourceLocks(locks) {
        const tbody = document.getElementById('os-mutex-locks-body');
        if (!tbody) return;

        if (!locks || locks.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="py-4 text-center text-xs text-slate-500 italic">No resources currently locked (All mutex locks available).</td></tr>`;
            return;
        }

        tbody.innerHTML = locks.map(l => `
            <tr class="border-b border-slate-800">
                <td class="py-2 px-3 font-mono text-xs text-amber-300">🔒 ${l.resource_id}</td>
                <td class="py-2 px-3 text-xs font-semibold text-white">${l.holder}</td>
                <td class="py-2 px-3 text-xs font-mono text-cyan-400">Session #${l.session_id}</td>
                <td class="py-2 px-3 text-[10px]"><span class="px-2 py-0.5 rounded font-bold bg-amber-500/20 text-amber-300">${l.mode}</span></td>
            </tr>
        `).join('');
    },

    renderOSStorageStats(stats) {
        const el = document.getElementById('os-storage-mb');
        if (el) el.innerText = `${stats.total_mb} MB (${stats.total_files} encrypted files)`;
    },

    // ------------------ FAMILY OVERVIEW ------------------
    async loadFamilyOverview() {
        try {
            const res = await API.getFamilyOverview();
            if (res.success && res.overview) {
                const ov = res.overview;
                document.getElementById('family-members-count').innerText = ov.member_count;
                document.getElementById('family-total-records').innerText = ov.total_records;

                const grid = document.getElementById('family-members-cards-grid');
                if (grid) {
                    grid.innerHTML = ov.members.map(m => `
                        <div class="glass-panel p-5 rounded-xl border border-slate-700/80">
                            <div class="flex items-center space-x-3 mb-3">
                                <div class="w-10 h-10 rounded-full bg-cyan-500/20 border border-cyan-500/40 text-cyan-400 font-bold flex items-center justify-center">
                                    ${m.full_name.charAt(0)}
                                </div>
                                <div>
                                    <h4 class="text-sm font-bold text-white">${m.full_name}</h4>
                                    <p class="text-xs text-cyan-400 font-mono">${m.health_id} • ${m.relationship}</p>
                                </div>
                            </div>
                            <div class="space-y-1.5 text-xs text-slate-300">
                                <p><span class="text-slate-500">Blood Group:</span> <strong class="text-white">${m.blood_group}</strong></p>
                                <p><span class="text-slate-500">Allergies:</span> <span class="${m.allergies && m.allergies !== 'None' ? 'text-red-400 font-bold' : 'text-slate-300'}">${m.allergies || 'None'}</span></p>
                                <p><span class="text-slate-500">Conditions:</span> ${m.existing_conditions || 'None'}</p>
                                <p><span class="text-slate-500">Contact:</span> ${m.emergency_contact_name || 'N/A'}</p>
                            </div>
                        </div>
                    `).join('');
                }
            }
        } catch (e) {
            console.error("Failed to load family overview:", e);
        }
    },

    // ------------------ AUDIT & ADMIN ------------------
    async loadAuditLogs() {
        try {
            const res = await API.getAuditLogs();
            if (res.success && res.audit_logs) {
                const tbody = document.getElementById('audit-logs-table-body');
                if (tbody) {
                    tbody.innerHTML = res.audit_logs.map(log => `
                        <tr class="border-b border-slate-800 text-xs hover:bg-slate-800/40">
                            <td class="py-2.5 px-3 font-mono text-slate-400">${log.timestamp}</td>
                            <td class="py-2.5 px-3 font-semibold text-white">${log.actor_name} <span class="text-[10px] text-slate-500 font-mono">(${log.actor_role})</span></td>
                            <td class="py-2.5 px-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-cyan-400 border border-slate-700">${log.action}</span></td>
                            <td class="py-2.5 px-3 text-slate-300">${log.details}</td>
                            <td class="py-2.5 px-3 font-mono text-[10px] text-emerald-400" title="${log.integrity_hash}">✓ ${log.integrity_hash ? log.integrity_hash.substring(0, 10) + '...' : 'OK'}</td>
                        </tr>
                    `).join('');
                }
            }
        } catch (e) {}
    },

    async loadAdminDashboard() {
        try {
            const statusRes = await API.getSystemStatus();
            if (statusRes.success && statusRes.status) {
                const s = statusRes.status;
                document.getElementById('admin-stat-users').innerText = s.active_users;
                document.getElementById('admin-stat-sessions').innerText = s.active_sessions;
                document.getElementById('admin-stat-requests').innerText = s.pending_requests;
                document.getElementById('admin-stat-emergencies').innerText = s.emergency_requests;
                document.getElementById('admin-stat-storage').innerText = `${s.storage_mb} MB`;
            }
        } catch (e) {}
        this.loadAuditLogs();
    },

    // ------------------ NOTIFICATIONS ------------------
    async loadNotifications() {
        if (!this.currentUser) return;
        try {
            const res = await API.getNotifications();
            if (res.success && res.notifications) {
                const unread = res.notifications.filter(n => !n.is_read).length;
                const badge = document.getElementById('notif-badge-count');
                if (badge) {
                    if (unread > 0) {
                        badge.innerText = unread;
                        badge.classList.remove('hidden');
                    } else {
                        badge.classList.add('hidden');
                    }
                }
                
                const list = document.getElementById('notif-dropdown-list');
                if (list) {
                    if (res.notifications.length === 0) {
                        list.innerHTML = `<p class="text-xs text-slate-500 p-3 text-center">No notifications yet.</p>`;
                    } else {
                        list.innerHTML = res.notifications.slice(0, 8).map(n => `
                            <div class="p-3 border-b border-slate-800 hover:bg-slate-800/60 transition ${n.is_read ? 'opacity-60' : 'bg-cyan-950/20'}">
                                <h5 class="text-xs font-bold text-white">${n.title}</h5>
                                <p class="text-[11px] text-slate-300 mt-0.5 leading-relaxed">${n.message}</p>
                                <span class="text-[10px] text-slate-500 font-mono mt-1 block">${n.created_at}</span>
                            </div>
                        `).join('');
                    }
                }
            }
        } catch (e) {}
    },

    // Helper
    getTimeOfDay() {
        const hour = new Date().getHours();
        if (hour < 12) return 'Morning';
        if (hour < 17) return 'Afternoon';
        return 'Evening';
    }
};

window.App = App;
document.addEventListener('DOMContentLoaded', () => App.init());
