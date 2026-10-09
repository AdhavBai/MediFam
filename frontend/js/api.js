/**
 * MediFamily OS - API Client & Transport Layer
 * Configurable base URL for LAN / Mobile / Internet deployment.
 */

const API = {
    // Dynamically use current origin (or fallback to window.location)
    BASE_URL: window.location.origin,

    getToken() {
        return localStorage.getItem('medifamily_token') || '';
    },

    setToken(token) {
        if (token) localStorage.setItem('medifamily_token', token);
        else localStorage.removeItem('medifamily_token');
    },

    getSessionToken() {
        return localStorage.getItem('medifamily_session_token') || '';
    },

    setSessionToken(token) {
        if (token) localStorage.setItem('medifamily_session_token', token);
        else localStorage.removeItem('medifamily_session_token');
    },

    getCurrentUser() {
        try {
            return JSON.parse(localStorage.getItem('medifamily_user') || 'null');
        } catch {
            return null;
        }
    },

    setCurrentUser(user) {
        if (user) localStorage.setItem('medifamily_user', JSON.stringify(user));
        else localStorage.removeItem('medifamily_user');
    },

    async request(endpoint, options = {}) {
        const url = `${this.BASE_URL}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        };

        const token = this.getToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const sessionToken = this.getSessionToken();
        if (sessionToken) {
            headers['X-Session-Token'] = sessionToken;
        }

        try {
            const response = await fetch(url, {
                ...options,
                headers
            });

            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                const errorMsg = data.error || `HTTP ${response.status}: ${response.statusText}`;
                throw new Error(errorMsg);
            }

            return data;
        } catch (err) {
            console.error(`API Error [${endpoint}]:`, err);
            throw err;
        }
    },

    // Auth
    login(username, password) {
        return this.request('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
    },

    getMe() {
        return this.request('/api/auth/me');
    },

    // Patients
    getPatientByHealthId(healthId) {
        return this.request(`/api/patients/${encodeURIComponent(healthId)}`);
    },

    getPatientRecords(patientId) {
        return this.request(`/api/patients/${patientId}/records`);
    },

    uploadRecord(patientId, recordData) {
        return this.request(`/api/patients/${patientId}/records`, {
            method: 'POST',
            body: JSON.stringify(recordData)
        });
    },

    deleteRecord(recordId) {
        return this.request(`/api/records/${recordId}`, {
            method: 'DELETE'
        });
    },

    getActiveSessions(patientId) {
        return this.request(`/api/patients/${patientId}/active-sessions`);
    },

    updateMedicalProfile(patientId, profileData) {
        return this.request(`/api/patients/${patientId}/profile`, {
            method: 'POST',
            body: JSON.stringify(profileData)
        });
    },

    // Access Control
    requestAccess(healthId, reason, durationMinutes = 15) {
        return this.request('/api/access/request', {
            method: 'POST',
            body: JSON.stringify({ health_id: healthId, reason, duration_minutes: durationMinutes })
        });
    },

    approveAccess(requestId) {
        return this.request(`/api/access/${requestId}/approve`, {
            method: 'POST'
        });
    },

    rejectAccess(requestId) {
        return this.request(`/api/access/${requestId}/reject`, {
            method: 'POST'
        });
    },

    revokeSession(sessionId) {
        return this.request(`/api/access/sessions/${sessionId}/revoke`, {
            method: 'POST'
        });
    },

    // Emergency Break-Glass
    requestEmergency(healthId, reason) {
        return this.request('/api/emergency/request', {
            method: 'POST',
            body: JSON.stringify({ health_id: healthId, reason })
        });
    },

    approveEmergency(requestId, verificationCode) {
        return this.request(`/api/emergency/${requestId}/approve`, {
            method: 'POST',
            body: JSON.stringify({ verification_code: verificationCode })
        });
    },

    getEmergencySummary(healthId) {
        return this.request(`/api/emergency/summary/${encodeURIComponent(healthId)}`);
    },

    // Family & Notifications
    getFamilyMembers(familyId) {
        return this.request(`/api/family/${familyId}/members`);
    },

    getFamilyOverview() {
        return this.request('/api/family/overview');
    },

    getNotifications() {
        return this.request('/api/notifications');
    },

    markNotificationRead(notificationId) {
        return this.request(`/api/notifications/${notificationId}/read`, {
            method: 'POST'
        });
    },

    // Audit & System
    getAuditLogs() {
        return this.request('/api/audit-logs');
    },

    getSystemStatus() {
        return this.request('/api/system/status');
    },

    getOSConcepts() {
        return this.request('/api/system/os-concepts');
    },

    // Demo Simulations
    simulateAccess() {
        return this.request('/api/demo/simulate-access', { method: 'POST' });
    },

    simulateEmergency() {
        return this.request('/api/demo/simulate-emergency', { method: 'POST' });
    },

    resetDemoData() {
        return this.request('/api/demo/reset', { method: 'POST' });
    }
};

window.API = API;
