/**
 * ESTACIÓN TERRENA — COMMON TELEMETRY UTILITIES & GLOBAL HEADER MANAGER
 * High-contrast aerospace ground station frontend suite
 */

// Apply saved theme immediately to prevent any white flash / FOUC
(function applyEarlyTheme() {
    try {
        const saved = localStorage.getItem("ground_station_theme") || "light";
        document.documentElement.setAttribute("data-theme", saved);
    } catch (e) {}
})();

// Fast element selector
window.$ = window.$ || (id => document.getElementById(id));
var $ = window.$;

// Numeric formatting with Argentine / Spanish locale (comma decimals)
window.fmt = window.fmt || function fmt(n, dec = 2) {
    const num = Number(n);
    return Number.isFinite(num)
        ? new Intl.NumberFormat("es-AR", { minimumFractionDigits: dec, maximumFractionDigits: dec }).format(num)
        : "---";
};
var fmt = window.fmt;

// Strict fixed-width signed tabular numeric formatting (+00.00 / -00.00)
window.fmtSigned = window.fmtSigned || function fmtSigned(n, dec = 2) {
    const num = Number(n);
    if (!Number.isFinite(num)) return " --- ";
    const sign = num > 0 ? "+" : (num < 0 ? "−" : "+");
    const absVal = Math.abs(num);
    const parts = absVal.toFixed(dec).split(".");
    const intPart = parts[0].padStart(2, "0");
    return `${sign}${intPart}.${parts[1] || ""}`;
};
var fmtSigned = window.fmtSigned;

// Format milliseconds into HH:MM:SS string
window.elapsed = window.elapsed || function elapsed(ms) {
    if (!Number.isFinite(ms) || ms < 0) return "00:00:00";
    const s = Math.floor(ms / 1000);
    const p = v => String(v).padStart(2, "0");
    return `${p(Math.floor(s / 3600))}:${p(Math.floor((s % 3600) / 60))}:${p(s % 60)}`;
};
var elapsed = window.elapsed;

// Canonical Spanish flight phase dictionary
window.PHASE_NAMES = window.PHASE_NAMES || {
    0: "PLATAFORMA",
    1: "MOTOR ENCENDIDO",
    2: "FIN DE EMPUJE",
    3: "FIN DE EMPUJE",
    4: "APOGEO",
    7: "APOGEO",
    8: "ORDEN DROGUE",
    15: "ORDEN DROGUE",
    16: "DROGUE DESPLEGADO",
    31: "DROGUE DESPLEGADO",
    32: "ORDEN PRINCIPAL",
    63: "ORDEN PRINCIPAL",
    64: "PRINCIPAL DESPLEGADO",
    127: "PRINCIPAL DESPLEGADO",
    128: "ATERRIZADO",
    255: "ATERRIZADO",
    STANDBY: "PLATAFORMA",
    POWERED: "MOTOR ENCENDIDO",
    BURNOUT: "FIN DE EMPUJE",
    APOGEE: "APOGEO",
    DROGUE_ORD: "ORDEN DROGUE",
    DROGUE_CONF: "DROGUE DESPLEGADO",
    MAIN_ORD: "ORDEN PRINCIPAL",
    MAIN_CONF: "PRINCIPAL DESPLEGADO",
    LANDED: "ATERRIZADO"
};
var PHASE_NAMES = window.PHASE_NAMES;

window.getPhaseName = window.getPhaseName || function getPhaseName(status) {
    if (status === null || status === undefined) return "---";
    return window.PHASE_NAMES[status] || String(status);
};
var getPhaseName = window.getPhaseName;

/**
 * Sliding 5-second packet loss and RX rate tracker
 */
window.PacketTracker = window.PacketTracker || class PacketTracker {
    constructor(windowMs = 5000) {
        this.windowMs = windowMs;
        this.lastSeq = null;
        this.seqWindow = [];     // Array of { t: epochMs, rec: int, lost: int }
        this.packetTimes = [];   // Array of epochMs
        this.lossPercent = 0.0;
        this.rxRate = 0.0;
        this.rxCount = 0;
    }

    recordPacket(seq, timestampMs = Date.now(), isHistory = false) {
        this.rxCount++;
        const now = timestampMs;

        let lostInStep = 0;
        if (Number.isFinite(seq)) {
            if (this.lastSeq !== null) {
                const expected = (this.lastSeq + 1) & 0xFFFF;
                if (seq !== expected) {
                    const diff = (seq - expected) & 0xFFFF;
                    if (diff < 1000) lostInStep = diff;
                }
            }
            this.lastSeq = seq;
        }

        this.seqWindow.push({ t: now, rec: 1, lost: lostInStep });

        if (!isHistory) {
            this.packetTimes.push(now);
        }
    }

    prune(now = Date.now()) {
        const cutoff = now - this.windowMs;

        // Prune packet rates
        let cutTimes = 0;
        while (cutTimes < this.packetTimes.length && this.packetTimes[cutTimes] < cutoff) {
            cutTimes++;
        }
        if (cutTimes > 0) this.packetTimes.splice(0, cutTimes);

        const span = this.packetTimes.length > 1 ? (this.packetTimes.at(-1) - this.packetTimes[0]) / 1000 : 0;
        this.rxRate = span > 0 ? (this.packetTimes.length - 1) / span : (this.packetTimes.length > 0 ? 1.0 : 0.0);

        // Prune packet loss window
        let cutSeq = 0;
        while (cutSeq < this.seqWindow.length && this.seqWindow[cutSeq].t < cutoff) {
            cutSeq++;
        }
        if (cutSeq > 0) this.seqWindow.splice(0, cutSeq);

        let recTotal = 0, lostTotal = 0;
        for (let i = 0; i < this.seqWindow.length; i++) {
            recTotal += this.seqWindow[i].rec;
            lostTotal += this.seqWindow[i].lost;
        }
        const total = recTotal + lostTotal;
        this.lossPercent = total > 0 ? (lostTotal / total) * 100 : 0.0;
    }
};
var PacketTracker = window.PacketTracker;

/**
 * Updates the unified 6-cell global header
 *
 * @param {Object} options
 * @param {number} [options.missionTimeMs] - Milliseconds since liftoff (or 0)
 * @param {string|number} [options.status] - Flight stage key or label
 * @param {number|null} [options.rssi] - RF RSSI in dBm
 * @param {number} [options.lossPercent] - Recent packet loss percentage
 * @param {boolean} [options.connected] - Link status boolean
 * @param {number|null} [options.lastPacketAt] - Epoch timestamp of last packet
 */
window.updateGlobalHeader = window.updateGlobalHeader || function updateGlobalHeader({
    missionTimeMs = 0,
    status = null,
    rssi = null,
    lossPercent = 0.0,
    connected = false,
    lastPacketAt = null,
    tempImu = null
} = {}) {
    const now = Date.now();
    const nowDate = new Date();
    const pad = n => String(n).padStart(2, "0");

    // 1. Local Time
    const localTimeEl = window.$("localTime");
    if (localTimeEl) {
        localTimeEl.textContent = `${pad(nowDate.getHours())}:${pad(nowDate.getMinutes())}:${pad(nowDate.getSeconds())}`;
    }

    // 2. Mission Clock
    const clockEl = window.$("clock");
    if (clockEl) {
        clockEl.textContent = window.elapsed(missionTimeMs);
    }

    // 3. Flight Phase
    const phaseEl = window.$("phase");
    if (phaseEl) {
        phaseEl.textContent = window.getPhaseName(status);
    }

    // 4. RF RSSI
    const rssiEl = window.$("rssi");
    if (rssiEl) {
        if (rssi !== null && Number.isFinite(Number(rssi))) {
            rssiEl.textContent = `${window.fmt(rssi, 0)} dBm`;
            rssiEl.className = "v num";
        } else {
            rssiEl.textContent = "N/D";
            rssiEl.className = "v num nd";
        }
    }

    // 5. Packet Loss
    const lossEl = window.$("lossPercent");
    if (lossEl) {
        lossEl.textContent = `${window.fmt(lossPercent, 1)} %`;
        if (lossPercent > 15) {
            lossEl.style.color = "var(--bad)";
        } else if (lossPercent > 5) {
            lossEl.style.color = "var(--warn)";
        } else {
            lossEl.style.color = "var(--ink)";
        }
    }

    // 6. IMU Temperature Pill (Cockpit Header Badge)
    const tempPillEl = window.$("tempPill");
    if (tempPillEl) {
        if (tempImu !== null && Number.isFinite(Number(tempImu))) {
            const t = Number(tempImu);
            tempPillEl.textContent = `IMU ${window.fmt(t, 1)} °C`;
            if (t >= 60) {
                tempPillEl.className = "temp-pill crit";
            } else if (t >= 45) {
                tempPillEl.className = "temp-pill warn";
            } else {
                tempPillEl.className = "temp-pill";
            }
        } else {
            tempPillEl.textContent = "IMU N/D";
            tempPillEl.className = "temp-pill";
        }
    }

    // 7. Link Status & Dot with >300ms Freeze Degradation
    const dotEl = window.$("linkDot");
    const linkStatusEl = window.$("linkStatus");
    const silenceMs = lastPacketAt !== null ? (now - lastPacketAt) : 0;
    const isFrozen = connected && lastPacketAt !== null && silenceMs > 300;
    const isStale = connected && lastPacketAt !== null && silenceMs > 2000;

    if (dotEl) {
        if (!connected) {
            dotEl.className = "dot";
        } else if (isFrozen) {
            dotEl.className = "dot warn";
        } else {
            dotEl.className = "dot online";
        }
    }

    if (linkStatusEl) {
        if (!connected) {
            linkStatusEl.textContent = "DESCONECTADO";
            linkStatusEl.style.color = "var(--bad)";
        } else if (isStale) {
            linkStatusEl.textContent = `DEGRADADO (+${(silenceMs / 1000).toFixed(1)}s)`;
            linkStatusEl.style.color = "var(--bad)";
        } else if (isFrozen) {
            linkStatusEl.textContent = `CONGELADO +${(silenceMs / 1000).toFixed(1)}s`;
            linkStatusEl.style.color = "var(--warn)";
        } else {
            linkStatusEl.textContent = "CONECTADO";
            linkStatusEl.style.color = "var(--ink)";
        }
    }
};
var updateGlobalHeader = window.updateGlobalHeader;

/**
 * Fetches the last 60 seconds of telemetry from the server
 * and feeds each frame to the provided callback
 */
window.fetchHistory60s = window.fetchHistory60s || async function fetchHistory60s(onFrame, onDone) {
    try {
        const response = await fetch("/api/history?seconds=60", { cache: "no-store" });
        if (!response.ok) return null;
        const data = await response.json();
        const frames = data.frames || [];

        if (typeof onFrame === "function") {
            for (let i = 0; i < frames.length; i++) {
                onFrame(frames[i], true);
            }
        }

        if (typeof onDone === "function") {
            onDone(data);
        }
        return data;
    } catch (err) {
        console.warn("Failed to fetch 60-second telemetry history:", err);
        return null;
    }
};
var fetchHistory60s = window.fetchHistory60s;

/**
 * Aerospace Cockpit Binary Annunciator updater (DROGUE & MAIN)
 * @param {string} cardId - DOM id of the annunciator card element
 * @param {string} stateId - DOM id of the annunciator state text element
 * @param {number|boolean} val - 0 (idle) or 1 (deployed)
 */
window.setAnnunciator = window.setAnnunciator || function setAnnunciator(cardId, stateId, val) {
    const card = window.$(cardId);
    const stateEl = window.$(stateId);
    if (!card || !stateEl) return;

    const isActive = Number(val) === 1;
    const targetClass = isActive ? "annun-card state-active" : "annun-card state-idle";
    if (card.className !== targetClass) {
        card.className = targetClass;
        if (isActive) {
            stateEl.innerHTML = '<span class="annun-icon">[OK]</span>[1: DESPLEGADO]';
        } else {
            stateEl.textContent = "[0: EN ESPERA]";
        }
    }
};
var setAnnunciator = window.setAnnunciator;
 
/**
 * Theme toggle manager (light/dark)
 */
window.initThemeManager = window.initThemeManager || function initThemeManager() {
    const updateThemeUI = () => {
        const isDark = document.documentElement.getAttribute("data-theme") === "dark";
        const icon = window.$("themeIcon");
        const label = window.$("themeLabel");
        if (icon) icon.textContent = isDark ? "☀️" : "🌙";
        if (label) label.textContent = isDark ? "CLARO" : "OSCURO";
    };

    const toggleTheme = () => {
        const cur = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
        const next = cur === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);
        try {
            localStorage.setItem("ground_station_theme", next);
        } catch (e) {}
        updateThemeUI();
        window.dispatchEvent(new CustomEvent("themechange", { detail: { theme: next } }));
    };

    updateThemeUI();

    const btn = window.$("btnThemeToggle");
    if (btn && !btn._themeBound) {
        btn._themeBound = true;
        btn.addEventListener("click", toggleTheme);
    }
};
var initThemeManager = window.initThemeManager;

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", window.initThemeManager);
} else {
    window.initThemeManager();
}
