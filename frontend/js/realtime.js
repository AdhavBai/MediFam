/**
 * MediFamily OS - Real-Time Event Bus & Audio Alert System
 * Implements persistent SSE connection with auto-reconnect, Web Audio synthesizer, and toast alerts.
 */

class RealtimeClient {
    constructor() {
        this.eventSource = null;
        this.isConnected = false;
        this.listeners = new Map();
        this.audioCtx = null;
    }

    init() {
        const token = API.getToken();
        if (!token) return;

        if (this.eventSource) {
            this.eventSource.close();
        }

        const url = `${API.BASE_URL}/api/events?token=${encodeURIComponent(token)}`;
        this.eventSource = new EventSource(url);

        this.eventSource.addEventListener('connected', (e) => {
            this.isConnected = true;
            this.updateConnectionStatus(true);
            console.log('[Realtime] Connected to MediFamily OS Live Event Stream');
        });

        // 1. In-App Notification
        this.eventSource.addEventListener('notification', (e) => {
            const data = JSON.parse(e.data);
            this.playNotificationSound(data.type === 'emergency_request');
            this.showToast(data.title, data.message, data.type === 'emergency_request' ? 'emergency' : 'info');
            this.trigger('notification', data);
        });

        // 2. Normal Access Approved
        this.eventSource.addEventListener('access_approved', (e) => {
            const data = JSON.parse(e.data);
            this.playNotificationSound(false);
            this.showToast('✓ Access Approved', data.message, 'success');
            this.trigger('access_approved', data);
        });

        // 3. Normal Access Rejected
        this.eventSource.addEventListener('access_rejected', (e) => {
            const data = JSON.parse(e.data);
            this.showToast('✗ Access Rejected', data.message, 'warning');
            this.trigger('access_rejected', data);
        });

        // 4. Emergency Break-Glass Approved
        this.eventSource.addEventListener('emergency_approved', (e) => {
            const data = JSON.parse(e.data);
            this.playNotificationSound(false);
            this.showToast('🚨 Emergency Access Granted', data.message, 'emergency');
            this.trigger('emergency_approved', data);
        });

        // 5. Access Revoked (Doctor screen locks immediately!)
        this.eventSource.addEventListener('access_revoked', (e) => {
            const data = JSON.parse(e.data);
            this.showToast('🔒 Access Revoked', data.message, 'warning');
            this.trigger('access_revoked', data);
        });

        // 6. System Reset
        this.eventSource.addEventListener('system_reset', (e) => {
            const data = JSON.parse(e.data);
            this.showToast('System Reset', data.message, 'info');
            this.trigger('system_reset', data);
        });

        this.eventSource.onerror = () => {
            this.isConnected = false;
            this.updateConnectionStatus(false);
        };
    }

    on(eventName, callback) {
        if (!this.listeners.has(eventName)) {
            this.listeners.set(eventName, []);
        }
        this.listeners.get(eventName).push(callback);
    }

    trigger(eventName, data) {
        if (this.listeners.has(eventName)) {
            this.listeners.get(eventName).forEach(cb => cb(data));
        }
    }

    updateConnectionStatus(connected) {
        const badge = document.getElementById('connection-status-badge');
        if (badge) {
            if (connected) {
                badge.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> <span class="text-xs text-emerald-300 font-medium">Server Connected</span>`;
                badge.className = "flex items-center space-x-1.5 px-2.5 py-1 bg-emerald-950/60 border border-emerald-800/60 rounded-full";
            } else {
                badge.innerHTML = `<span class="w-2 h-2 rounded-full bg-amber-400"></span> <span class="text-xs text-amber-300 font-medium">Reconnecting...</span>`;
                badge.className = "flex items-center space-x-1.5 px-2.5 py-1 bg-amber-950/60 border border-amber-800/60 rounded-full";
            }
        }
    }

    playNotificationSound(isEmergency = false) {
        try {
            if (!this.audioCtx) {
                this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            }
            if (this.audioCtx.state === 'suspended') {
                this.audioCtx.resume();
            }

            const osc = this.audioCtx.createOscillator();
            const gain = this.audioCtx.createGain();
            osc.connect(gain);
            gain.connect(this.audioCtx.destination);

            if (isEmergency) {
                // High urgency emergency dual-tone siren
                osc.type = 'sawtooth';
                osc.frequency.setValueAtTime(880, this.audioCtx.currentTime); // A5
                osc.frequency.setValueAtTime(587.33, this.audioCtx.currentTime + 0.15); // D5
                osc.frequency.setValueAtTime(880, this.audioCtx.currentTime + 0.3);
                gain.gain.setValueAtTime(0.3, this.audioCtx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, this.audioCtx.currentTime + 0.6);
                osc.start();
                osc.stop(this.audioCtx.currentTime + 0.6);
            } else {
                // Gentle pleasant medical notification chime
                osc.type = 'sine';
                osc.frequency.setValueAtTime(523.25, this.audioCtx.currentTime); // C5
                osc.frequency.setValueAtTime(659.25, this.audioCtx.currentTime + 0.1); // E5
                osc.frequency.setValueAtTime(783.99, this.audioCtx.currentTime + 0.2); // G5
                gain.gain.setValueAtTime(0.2, this.audioCtx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, this.audioCtx.currentTime + 0.5);
                osc.start();
                osc.stop(this.audioCtx.currentTime + 0.5);
            }
        } catch (e) {
            // Audio context policy fallback
        }
    }

    showToast(title, message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        let typeClasses = "bg-slate-800 border-slate-700 text-slate-100";
        let iconHtml = `<i data-lucide="info" class="w-5 h-5 text-cyan-400"></i>`;

        if (type === 'emergency') {
            typeClasses = "bg-red-950/95 border-red-500/80 text-red-100 emergency-glow";
            iconHtml = `<i data-lucide="alert-triangle" class="w-5 h-5 text-red-400"></i>`;
        } else if (type === 'success') {
            typeClasses = "bg-emerald-950/95 border-emerald-500/80 text-emerald-100";
            iconHtml = `<i data-lucide="check-circle-2" class="w-5 h-5 text-emerald-400"></i>`;
        } else if (type === 'warning') {
            typeClasses = "bg-amber-950/95 border-amber-500/80 text-amber-100";
            iconHtml = `<i data-lucide="shield-alert" class="w-5 h-5 text-amber-400"></i>`;
        }

        toast.className = `p-4 rounded-xl border shadow-2xl flex items-start space-x-3 max-w-sm toast-animate ${typeClasses}`;
        toast.innerHTML = `
            <div class="flex-shrink-0 mt-0.5">${iconHtml}</div>
            <div class="flex-1 min-w-0">
                <h4 class="text-sm font-bold tracking-tight">${title}</h4>
                <p class="text-xs opacity-90 mt-0.5 leading-relaxed">${message}</p>
            </div>
            <button class="text-slate-400 hover:text-white" onclick="this.parentElement.remove()">
                <i data-lucide="x" class="w-4 h-4"></i>
            </button>
        `;

        container.appendChild(toast);
        if (window.lucide) lucide.createIcons();

        setTimeout(() => {
            if (toast.parentElement) {
                toast.style.opacity = '0';
                toast.style.transition = 'opacity 0.3s ease';
                setTimeout(() => toast.remove(), 300);
            }
        }, 6000);
    }
}

window.realtime = new RealtimeClient();
