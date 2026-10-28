/**
 * ==============================================================================
 * CanSat CONAE 2026–2027: Pure Client-Side Demo Flight Simulator & Pages Engine
 * ==============================================================================
 * Automatically activates on:
 *   - GitHub Pages (*.github.io)
 *   - Static hosts (*.pages.dev, *.netlify.app, *.vercel.app, file://)
 *   - URL parameter: ?demo=1 or #demo
 *
 * Capabilities:
 *   1. Full 240-second flight profile (Pad -> Boost -> Apogee -> Drogue C3 -> Main C4 -> Landed).
 *   2. Generates official 22-field CONAE ASCII CSV telemetry at 1 Hz.
 *   3. Mocks WebSocket connection & dispatches live telemetry frames to dashboard.
 *   4. Intercepts /api/command, executing telecommands in real-time (CAL, ST, PC, BATT, SIM, START).
 *   5. Intercepts /api/export/csv, generating instantaneous Flight_1000.csv client-side downloads.
 *   6. Floating Demo Controller HUD with Play/Pause, speed (1x/2x/5x/10x), scrubber, & phase jumps.
 * ==============================================================================
 */

(function initCanSatDemoEngine() {
    'use strict';

    // --------------------------------------------------------------------------
    // 1. DEMO MODE DETECTION
    // --------------------------------------------------------------------------
    function detectDemoMode() {
        try {
            const params = new URLSearchParams(window.location.search);
            const demoParam = params.get('demo') || params.get('mode');

            if (demoParam === '0' || demoParam === 'false' || demoParam === 'live') {
                sessionStorage.removeItem('cansat_demo_mode');
                return false;
            }
            if (demoParam === '1' || demoParam === 'true' || demoParam === 'demo' || window.location.hash === '#demo') {
                sessionStorage.setItem('cansat_demo_mode', '1');
                return true;
            }
            if (sessionStorage.getItem('cansat_demo_mode') === '1') {
                return true;
            }

            const host = (window.location.hostname || '').toLowerCase();
            const isStaticHost =
                window.location.protocol === 'file:' ||
                host.endsWith('.github.io') ||
                host.endsWith('.pages.dev') ||
                host.endsWith('.netlify.app') ||
                host.endsWith('.vercel.app');

            if (isStaticHost) {
                sessionStorage.setItem('cansat_demo_mode', '1');
                return true;
            }
        } catch (e) {
            console.warn('[DemoMode] Detection check error', e);
        }
        return false;
    }

    const IS_DEMO = detectDemoMode();
    window.IS_DEMO_MODE = IS_DEMO;

    // Public toggles for header button
    window.enterDemoMode = function() {
        sessionStorage.setItem('cansat_demo_mode', '1');
        const url = new URL(window.location.href);
        url.searchParams.set('demo', '1');
        window.location.href = url.toString();
    };

    window.exitDemoMode = function() {
        sessionStorage.removeItem('cansat_demo_mode');
        const url = new URL(window.location.href);
        url.searchParams.delete('demo');
        url.searchParams.delete('mode');
        window.location.href = url.toString();
    };

    // --------------------------------------------------------------------------
    // 2. SIMULATION CONSTANTS & FLIGHT PROFILE (CONAE BASES §4, C3, C4)
    // --------------------------------------------------------------------------
    const CYCLE_DURATION_S = 240.0;
    const TEAM_ID = '1000';
    const BASE_LAT = -31.5238;
    const BASE_LON = -64.4642;
    const BASE_ELEVATION_MSL = 750.0; // Ground elevation at Falda del Cañete (m MSL)
    const BASE_PRESSURE = 93.5;       // Ambient pressure at 750m ASL (kPa)
    const BASE_TEMP = 21.5;           // Ground ambient temperature (°C)

    const LAUNCH_TIME_S = 20.0;
    const APOGEE_TIME_S = 45.0;
    const MAIN_CHUTE_TIME_S = 115.0;
    const LANDED_TIME_S = 200.0;

    let simTimeSec = 0.0;
    try {
        const savedT = parseFloat(sessionStorage.getItem('cansat_sim_time'));
        if (Number.isFinite(savedT) && savedT >= 0 && savedT < CYCLE_DURATION_S) {
            simTimeSec = savedT;
        }
    } catch (e) {}

    const demoEngine = {
        simTimeSec,
        speed: 1,
        paused: false,
        minimized: false,
        packetCount: Math.max(1, Math.floor(simTimeSec)),
        altitudeOffset: 0.0,
        mode: 'F',
        lastCmdEcho: 'BOOT_OK',
        sockets: new Set(),
        recordedHistory: []
    };
    window.demoEngine = demoEngine;

    // Deterministic pseudo-random helper
    function detNoise(seed, minVal, maxVal) {
        const x = Math.sin(seed * 12.9898 + 78.233) * 43758.5453;
        const frac = x - Math.floor(x);
        return minVal + frac * (maxVal - minVal);
    }

    /**
     * Compute instantaneous CanSat flight physics and 22-field telemetry packet
     */
    function calculateFlightFrame(tSec, seqNum, epochMs) {
        const t = ((tSec % CYCLE_DURATION_S) + CYCLE_DURATION_S) % CYCLE_DURATION_S;
        const seed = Math.round(t * 10);

        let state = 'LAUNCH_PAD';
        let rawAltitude = 0.0;
        let vz = 0.0;
        let accelR = detNoise(seed + 1, -0.02, 0.02);
        let accelP = detNoise(seed + 2, -0.02, 0.02);
        let accelY = 9.81 + detNoise(seed + 3, -0.03, 0.03);
        let gyroR = detNoise(seed + 4, -0.1, 0.1);
        let gyroP = detNoise(seed + 5, -0.1, 0.1);
        let gyroY = detNoise(seed + 6, -0.1, 0.1);
        let cmdEcho = demoEngine.lastCmdEcho;
        let solarV = 0.0;

        if (t < LAUNCH_TIME_S) {
            // 1. LAUNCH_PAD (0 - 20s)
            state = 'LAUNCH_PAD';
            rawAltitude = detNoise(seed + 7, -0.05, 0.05);
            vz = 0.0;
        } else if (t < APOGEE_TIME_S) {
            // 2. ASCENT (20 - 45s): Rocket burn to 1500m
            state = 'ASCENT';
            const progress = (t - LAUNCH_TIME_S) / (APOGEE_TIME_S - LAUNCH_TIME_S);
            rawAltitude = 1500.0 * Math.sin(progress * (Math.PI / 2.0));
            vz = (1500.0 * (Math.PI / 2.0) * Math.cos(progress * (Math.PI / 2.0))) / (APOGEE_TIME_S - LAUNCH_TIME_S);
            accelY = 9.81 + 32.0 * (1.0 - progress) + detNoise(seed + 8, -1.5, 1.5);
            accelR = 2.5 * Math.sin(t) + detNoise(seed + 9, -0.2, 0.2);
            accelP = 2.1 * Math.cos(t) + detNoise(seed + 10, -0.2, 0.2);
            gyroR = 45.0 * (1.0 - progress) + detNoise(seed + 11, -1.0, 1.0);
            gyroP = 12.0 + detNoise(seed + 12, -0.5, 0.5);
            gyroY = 8.0 + detNoise(seed + 13, -0.5, 0.5);
        } else if (t >= APOGEE_TIME_S && t < APOGEE_TIME_S + 1.5) {
            // 3. APOGEE & SEPARATION EVENT (45s): Automatic mission start trigger (X3)
            state = 'APOGEE';
            rawAltitude = 1500.0;
            vz = 0.0;
            cmdEcho = 'MISSION_START';
            demoEngine.lastCmdEcho = 'MISSION_START';
            accelY = 0.0;
            solarV = 4.95;
        } else if (t < MAIN_CHUTE_TIME_S) {
            // 4. DROGUE PARACHUTE DESCENT (45 - 115s): 15 ± 3 m/s (C3 compliant)
            state = 'DESCENT';
            const descentRate = 14.8; // m/s
            rawAltitude = Math.max(450.0, 1500.0 - descentRate * (t - APOGEE_TIME_S));
            vz = -descentRate;
            accelY = 9.81 + detNoise(seed + 14, -0.2, 0.2);
            accelR = 3.2 * Math.sin(t * 1.5) + detNoise(seed + 15, -0.3, 0.3);
            accelP = 2.8 * Math.cos(t * 1.5) + detNoise(seed + 16, -0.3, 0.3);
            gyroR = 22.0 * Math.sin(t) + detNoise(seed + 17, -0.8, 0.8);
            gyroP = 18.0 * Math.cos(t) + detNoise(seed + 18, -0.8, 0.8);
            gyroY = 9.0 * Math.sin(t * 0.8) + detNoise(seed + 19, -0.5, 0.5);
            solarV = 4.95;
        } else if (t < LANDED_TIME_S) {
            // 5. MAIN PARACHUTE DESCENT (115 - 200s): 5 ± 3 m/s (C4 compliant)
            state = 'DESCENT';
            const descentRate = 5.2; // m/s
            rawAltitude = Math.max(0.0, 450.0 - descentRate * (t - MAIN_CHUTE_TIME_S));
            vz = -descentRate;
            accelY = 9.81 + detNoise(seed + 20, -0.05, 0.05);
            accelR = 0.8 * Math.sin(t) + detNoise(seed + 21, -0.08, 0.08);
            accelP = 0.7 * Math.cos(t) + detNoise(seed + 22, -0.08, 0.08);
            gyroR = 4.5 * Math.sin(t * 0.5) + detNoise(seed + 23, -0.2, 0.2);
            gyroP = 3.8 * Math.cos(t * 0.5) + detNoise(seed + 24, -0.2, 0.2);
            gyroY = 2.0 * Math.sin(t * 0.4) + detNoise(seed + 25, -0.2, 0.2);
            solarV = 4.95;
            if (rawAltitude <= 0.0) {
                state = 'LANDED';
                rawAltitude = 0.0;
                vz = 0.0;
            }
        } else {
            // 6. LANDED (200s - 240s)
            state = 'LANDED';
            rawAltitude = 0.0;
            vz = 0.0;
            accelY = 9.81;
            solarV = 0.05;
        }

        // Relative altitude after zero-calibration offset (G1)
        const relAltitude = Math.max(0.0, rawAltitude - demoEngine.altitudeOffset);

        // Barometric & thermal lapse: P = P0 * exp(-h / 8400), T = T0 - 0.0065 * h
        const pressure = Number((BASE_PRESSURE * Math.exp(-relAltitude / 8400.0)).toFixed(2));
        const temperature = Number((BASE_TEMP - relAltitude * 0.0065).toFixed(1));

        // Battery discharge curve
        const voltage = Number(Math.max(3.40, 3.92 - t * 0.0008).toFixed(2));
        const current = Number((0.15 + 0.05 * (Math.round(t) % 4 === 0 ? 1 : 0)).toFixed(2));

        // GPS WGS84 coordinates with realistic wind drift during descent
        const drift = (t >= LAUNCH_TIME_S) ? (t - LAUNCH_TIME_S) : 0;
        const gpsLatitude = Number((BASE_LAT + 0.000008 * drift + detNoise(seed + 26, -0.000002, 0.000002)).toFixed(6));
        const gpsLongitude = Number((BASE_LON + 0.000012 * drift + detNoise(seed + 27, -0.000002, 0.000002)).toFixed(6));
        const gpsAltitude = Number((BASE_ELEVATION_MSL + relAltitude).toFixed(1));
        const gpsSats = 12;

        // UTC Mission Time string
        const missionDate = new Date(epochMs);
        const missionTimeStr = missionDate.toTimeString().substring(0, 8);

        // Raw CSV line matching CONAE specification:
        // TEAM_ID, MISSION_TIME, PACKET_COUNT, MODE, STATE, ALTITUDE, TEMPERATURE, PRESSURE,
        // VOLTAGE, CURRENT, GYRO_R, GYRO_P, GYRO_Y, ACCEL_R, ACCEL_P, ACCEL_Y,
        // GPS_TIME, GPS_ALTITUDE, GPS_LATITUDE, GPS_LONGITUDE, GPS_SATS, CMD_ECHO,,SOLAR_V:...,PWR_STATUS:OK
        const rawLine = `${TEAM_ID},${missionTimeStr},${seqNum},${demoEngine.mode},${state},${relAltitude.toFixed(1)},${temperature.toFixed(1)},${pressure.toFixed(2)},${voltage.toFixed(2)},${current.toFixed(2)},${gyroR.toFixed(1)},${gyroP.toFixed(1)},${gyroY.toFixed(1)},${accelR.toFixed(2)},${accelP.toFixed(2)},${accelY.toFixed(2)},${missionTimeStr},${gpsAltitude.toFixed(1)},${gpsLatitude.toFixed(6)},${gpsLongitude.toFixed(6)},${gpsSats},${cmdEcho},,SOLAR_V:${solarV.toFixed(2)},PWR_STATUS:OK`;

        return {
            type: 'telemetry',
            timestamp: epochMs / 1000,
            raw_line: rawLine,
            data: {
                TEAM_ID,
                MISSION_TIME: missionTimeStr,
                PACKET_COUNT: seqNum,
                MODE: demoEngine.mode,
                STATE: state,
                ALTITUDE: Number(relAltitude.toFixed(1)),
                TEMPERATURE: temperature,
                PRESSURE: pressure,
                VOLTAGE: voltage,
                CURRENT: current,
                GYRO_R: Number(gyroR.toFixed(1)),
                GYRO_P: Number(gyroP.toFixed(1)),
                GYRO_Y: Number(gyroY.toFixed(1)),
                ACCEL_R: Number(accelR.toFixed(2)),
                ACCEL_P: Number(accelP.toFixed(2)),
                ACCEL_Y: Number(accelY.toFixed(2)),
                GPS_TIME: missionTimeStr,
                GPS_ALTITUDE: gpsAltitude,
                GPS_LATITUDE: gpsLatitude,
                GPS_LONGITUDE: gpsLongitude,
                GPS_SATS: gpsSats,
                CMD_ECHO: cmdEcho,
                OPTIONAL_DATA: `SOLAR_V:${solarV.toFixed(2)},PWR_STATUS:OK`
            },
            statistics: {
                received: seqNum,
                rx_count: seqNum,
                frames_received: seqNum,
                lost: 0,
                lost_count: 0,
                invalid: 0,
                loss_percent: 0.0,
                rate_hz: 1.0,
                vertical_velocity: Number(vz.toFixed(1))
            }
        };
    }

    // --------------------------------------------------------------------------
    // 3. MOCK WEBSOCKET & FETCH INTERCEPTORS
    // --------------------------------------------------------------------------
    if (IS_DEMO) {
        console.log('[DemoMode] CanSat client-side simulation engine ACTIVE');

        // Mock WebSocket
        class DemoWebSocket {
            constructor(url, protocols) {
                this.url = url;
                this.protocols = protocols;
                this.readyState = DemoWebSocket.CONNECTING;
                this.onopen = null;
                this.onmessage = null;
                this.onerror = null;
                this.onclose = null;

                demoEngine.sockets.add(this);

                setTimeout(() => {
                    if (this.readyState !== DemoWebSocket.CONNECTING) return;
                    this.readyState = DemoWebSocket.OPEN;
                    if (typeof this.onopen === 'function') {
                        this.onopen({ type: 'open' });
                    }
                    // Initial connection message
                    if (typeof this.onmessage === 'function') {
                        this.onmessage({ data: JSON.stringify({ type: 'connection', connected: true }) });
                    }
                }, 100);
            }

            close() {
                this.readyState = DemoWebSocket.CLOSED;
                demoEngine.sockets.delete(this);
                if (typeof this.onclose === 'function') {
                    this.onclose({ type: 'close', wasClean: true });
                }
            }

            send(data) {
                console.log('[DemoWebSocket] Received client message:', data);
            }
        }
        DemoWebSocket.CONNECTING = 0;
        DemoWebSocket.OPEN = 1;
        DemoWebSocket.CLOSING = 2;
        DemoWebSocket.CLOSED = 3;

        window.WebSocket = DemoWebSocket;

        // Mock fetch interceptor
        const originalFetch = window.fetch;
        window.fetch = async function demoFetch(input, init) {
            const urlStr = typeof input === 'string' ? input : (input && input.url ? input.url : '');

            // 1. Telecommand POST /api/command
            if (urlStr.includes('/api/command')) {
                let body = {};
                try {
                    body = typeof init.body === 'string' ? JSON.parse(init.body) : (init.body || {});
                } catch (e) {}

                const action = body.action || '';
                const cmd = body.command || '';
                let executed = cmd || action;

                if (action === 'calibrate_zero' || cmd.includes('CAL')) {
                    demoEngine.altitudeOffset = calculateFlightFrame(demoEngine.simTimeSec, demoEngine.packetCount, Date.now()).data.ALTITUDE + demoEngine.altitudeOffset;
                    demoEngine.lastCmdEcho = 'CAL';
                    executed = 'CMD,1000,CAL';
                } else if (action === 'set_time' || cmd.includes('ST')) {
                    demoEngine.lastCmdEcho = 'ST';
                    executed = 'CMD,1000,ST,' + new Date().toTimeString().substring(0, 8);
                } else if (action === 'reset_packet_count' || cmd.includes('PC')) {
                    demoEngine.packetCount = 0;
                    demoEngine.lastCmdEcho = 'PC_RESET';
                    executed = 'CMD,1000,PC,0';
                } else if (action === 'request_battery_solar' || cmd.includes('BATT')) {
                    demoEngine.lastCmdEcho = 'BATT_OK';
                    executed = 'CMD,1000,BATT';
                } else if (action === 'sim_enable' || cmd.includes('SIM')) {
                    demoEngine.mode = 'S';
                    demoEngine.lastCmdEcho = 'SIM_MODE';
                    executed = 'CMD,1000,SIM,ENABLE';
                } else if (action === 'mission_start' || cmd.includes('START')) {
                    if (demoEngine.simTimeSec < LAUNCH_TIME_S) {
                        demoEngine.simTimeSec = LAUNCH_TIME_S;
                    }
                    demoEngine.lastCmdEcho = 'LAUNCHED';
                    executed = 'CMD,1000,START';
                } else {
                    demoEngine.lastCmdEcho = cmd ? cmd.substring(0, 16) : 'ACK';
                }

                // Broadcast command dispatched to mock WebSockets
                for (const ws of demoEngine.sockets) {
                    if (ws.readyState === DemoWebSocket.OPEN && typeof ws.onmessage === 'function') {
                        ws.onmessage({
                            data: JSON.stringify({
                                type: 'command_dispatched',
                                command: executed,
                                status: 'SENT',
                                timestamp: Date.now() / 1000
                            })
                        });
                    }
                }

                return new Response(JSON.stringify({
                    status: 'SENT',
                    command: executed,
                    timestamp: Date.now() / 1000
                }), { status: 200, headers: { 'Content-Type': 'application/json' } });
            }

            // 2. CSV Export Handover /api/export/csv
            if (urlStr.includes('/api/export/csv')) {
                let csvRows = ['TEAM_ID,MISSION_TIME,PACKET_COUNT,MODE,STATE,ALTITUDE,TEMPERATURE,PRESSURE,VOLTAGE,CURRENT,GYRO_R,GYRO_P,GYRO_Y,ACCEL_R,ACCEL_P,ACCEL_Y,GPS_TIME,GPS_ALTITUDE,GPS_LATITUDE,GPS_LONGITUDE,GPS_SATS,CMD_ECHO,OPTIONAL_DATA'];

                // Sample points from T=0 up to current simTimeSec
                const endT = Math.max(1, Math.floor(demoEngine.simTimeSec));
                const epochBase = Date.now() - (endT * 1000);
                for (let s = 0; s <= endT; s++) {
                    const f = calculateFlightFrame(s, s + 1, epochBase + (s * 1000));
                    csvRows.push(f.raw_line.replace(',,', ','));
                }

                const csvBlob = new Blob([csvRows.join('\r\n') + '\r\n'], { type: 'text/csv' });
                return new Response(csvBlob, {
                    status: 200,
                    headers: {
                        'Content-Type': 'text/csv',
                        'Content-Disposition': 'attachment; filename="Flight_1000.csv"'
                    }
                });
            }

            // 3. Telemetry History /api/history
            if (urlStr.includes('/api/history')) {
                const frames = [];
                const count = Math.min(60, Math.max(10, Math.floor(demoEngine.simTimeSec)));
                const nowMs = Date.now();
                for (let i = count; i >= 0; i--) {
                    const tSample = Math.max(0, demoEngine.simTimeSec - i);
                    frames.push(calculateFlightFrame(tSample, Math.max(1, demoEngine.packetCount - i), nowMs - (i * 1000)));
                }
                return new Response(JSON.stringify({ frames }), {
                    status: 200,
                    headers: { 'Content-Type': 'application/json' }
                });
            }

            // 4. API Status /api/status
            if (urlStr.includes('/api/status')) {
                return new Response(JSON.stringify({
                    connected: true,
                    team_id: TEAM_ID,
                    mode: demoEngine.mode,
                    frames_received: demoEngine.packetCount,
                    statistics: {
                        received: demoEngine.packetCount,
                        rx_count: demoEngine.packetCount,
                        lost: 0,
                        lost_count: 0,
                        invalid: 0,
                        loss_percent: 0.0,
                        rate_hz: 1.0,
                        vertical_velocity: 0.0
                    },
                    storage: {
                        primary_csv: 'data/Flight_1000.csv',
                        backup_csv: 'data/backup/Flight_1000.csv'
                    }
                }), { status: 200, headers: { 'Content-Type': 'application/json' } });
            }

            return originalFetch(input, init);
        };

        // ----------------------------------------------------------------------
        // 4. SIMULATION HEARTBEAT TICK LOOP (1 Hz nominal)
        // ----------------------------------------------------------------------
        setInterval(() => {
            if (demoEngine.paused) return;

            const dt = 1.0 * demoEngine.speed;
            demoEngine.simTimeSec = (demoEngine.simTimeSec + dt) % CYCLE_DURATION_S;
            demoEngine.packetCount++;

            try {
                sessionStorage.setItem('cansat_sim_time', demoEngine.simTimeSec.toFixed(1));
            } catch (e) {}

            const frame = calculateFlightFrame(demoEngine.simTimeSec, demoEngine.packetCount, Date.now());

            for (const ws of demoEngine.sockets) {
                if (ws.readyState === DemoWebSocket.OPEN && typeof ws.onmessage === 'function') {
                    ws.onmessage({ data: JSON.stringify(frame) });
                }
            }

            updateDemoHudUI();
        }, 1000);
    }

    // --------------------------------------------------------------------------
    // 5. DEMO CONTROLLER FLOATING HUD & UI INTEGRATION
    // --------------------------------------------------------------------------
    function jumpToSimTime(targetSec) {
        demoEngine.simTimeSec = Math.max(0, Math.min(CYCLE_DURATION_S - 1, targetSec));
        demoEngine.packetCount = Math.max(1, Math.floor(demoEngine.simTimeSec));
        try {
            sessionStorage.setItem('cansat_sim_time', demoEngine.simTimeSec.toFixed(1));
        } catch (e) {}

        const frame = calculateFlightFrame(demoEngine.simTimeSec, demoEngine.packetCount, Date.now());
        for (const ws of demoEngine.sockets) {
            if (ws.readyState === 1 && typeof ws.onmessage === 'function') {
                ws.onmessage({ data: JSON.stringify(frame) });
            }
        }
        updateDemoHudUI();
    }
    window.jumpToDemoTime = jumpToSimTime;

    function getPhaseName(t) {
        if (t < LAUNCH_TIME_S) return 'LAUNCH PAD';
        if (t < APOGEE_TIME_S) return 'BOOST / ASCENT';
        if (t < APOGEE_TIME_S + 2.0) return 'APOGEE & SEP';
        if (t < MAIN_CHUTE_TIME_S) return 'DROGUE (C3 15m/s)';
        if (t < LANDED_TIME_S) return 'MAIN (C4 5m/s)';
        return 'TOUCHDOWN (0m)';
    }

    function updateDemoHudUI() {
        if (!IS_DEMO) return;
        const timeEl = document.getElementById('demoHudTime');
        const sliderEl = document.getElementById('demoHudSlider');
        const phaseEl = document.getElementById('demoHudPhase');

        if (timeEl) timeEl.textContent = `T+${demoEngine.simTimeSec.toFixed(0).padStart(3, '0')}s / ${CYCLE_DURATION_S}s`;
        if (sliderEl && document.activeElement !== sliderEl) sliderEl.value = demoEngine.simTimeSec;
        if (phaseEl) phaseEl.textContent = getPhaseName(demoEngine.simTimeSec);

        // Highlight active phase preset button
        const presets = document.querySelectorAll('.demo-preset-btn');
        presets.forEach(btn => {
            const start = parseFloat(btn.dataset.start || 0);
            const end = parseFloat(btn.dataset.end || 0);
            const active = demoEngine.simTimeSec >= start && demoEngine.simTimeSec < end;
            btn.classList.toggle('active', active);
        });
    }

    function mountDemoHud() {
        if (!IS_DEMO || document.getElementById('demoControlHud')) return;

        // Inject HUD CSS
        const style = document.createElement('style');
        style.textContent = `
            .demo-hud {
                position: fixed;
                bottom: 80px;
                right: 12px;
                z-index: 99999;
                background: #0f172a;
                color: #ffffff;
                border: 2px solid #38bdf8;
                border-radius: 6px;
                box-shadow: 0 8px 24px rgba(0,0,0,0.45);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                font-size: 11pt;
                width: 320px;
                transition: transform 0.2s ease, opacity 0.2s ease;
                user-select: none;
            }
            .demo-hud.minimized {
                width: auto;
                bottom: 78px;
            }
            .demo-hud-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 6px 10px;
                background: #1e293b;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                border-bottom: 1px solid #334155;
            }
            .demo-hud-badge {
                font-size: 10pt;
                font-weight: 950;
                color: #38bdf8;
                display: flex;
                align-items: center;
                gap: 5px;
            }
            .demo-hud-btn {
                background: #334155;
                color: #ffffff;
                border: 1px solid #64748b;
                padding: 2px 7px;
                border-radius: 3px;
                font-size: 9.5pt;
                font-weight: 800;
                cursor: pointer;
                transition: background 0.15s ease;
            }
            .demo-hud-btn:hover { background: #475569; }
            .demo-hud-btn.active {
                background: #0284c7;
                border-color: #38bdf8;
                color: #ffffff;
            }
            .demo-hud-btn.play-btn {
                background: #0284c7;
                font-size: 11pt;
                padding: 2px 9px;
            }
            .demo-hud-btn.play-btn.paused {
                background: #ea580c;
            }
            .demo-hud-body {
                padding: 8px 10px;
                display: flex;
                flex-direction: column;
                gap: 6px;
            }
            .demo-hud-slider-wrap {
                display: flex;
                flex-direction: column;
                gap: 2px;
            }
            .demo-hud-slider {
                width: 100%;
                cursor: pointer;
                accent-color: #38bdf8;
            }
            .demo-hud-presets {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 4px;
            }
            .demo-preset-btn {
                font-size: 8.5pt;
                padding: 4px 2px;
                text-align: center;
            }
            .demo-header-tag {
                background: #0284c7;
                color: #ffffff;
                font-size: 9pt;
                font-weight: 900;
                padding: 2px 7px;
                border-radius: 3px;
                text-decoration: none;
                cursor: pointer;
                border: 1px solid #38bdf8;
                text-transform: uppercase;
                margin-left: 8px;
            }
            .demo-header-tag.live-btn {
                background: #f1f5f9;
                color: #0f172a;
                border-color: #cbd5e1;
            }
            .demo-header-tag.live-btn:hover {
                background: #e2e8f0;
            }
        `;
        document.head.appendChild(style);

        // Build DOM
        const hud = document.createElement('div');
        hud.id = 'demoControlHud';
        hud.className = 'demo-hud';
        hud.innerHTML = `
            <div class="demo-hud-header">
                <span class="demo-hud-badge">
                    🚀 <span id="demoHudPhase">LAUNCH PAD</span>
                </span>
                <div style="display:flex; align-items:center; gap:5px;">
                    <button type="button" class="demo-hud-btn play-btn" id="demoBtnPlay" title="Play / Pause">⏸</button>
                    <button type="button" class="demo-hud-btn" id="demoBtnSpeed" title="Speed">1x</button>
                    <button type="button" class="demo-hud-btn" id="demoBtnMin" title="Minimize / Expand">▼</button>
                </div>
            </div>
            <div class="demo-hud-body" id="demoHudBody">
                <div class="demo-hud-slider-wrap">
                    <div style="display:flex; justify-content:space-between; font-size:9pt; color:#94a3b8; font-family:monospace;">
                        <span>TIMELINE SCRUBBER</span>
                        <span id="demoHudTime" style="color:#ffffff; font-weight:800;">T+000s / 240s</span>
                    </div>
                    <input type="range" class="demo-hud-slider" id="demoHudSlider" min="0" max="${CYCLE_DURATION_S}" step="1" value="${demoEngine.simTimeSec}">
                </div>
                <div class="demo-hud-presets">
                    <button type="button" class="demo-hud-btn demo-preset-btn" data-time="0" data-start="0" data-end="20">PAD (0s)</button>
                    <button type="button" class="demo-hud-btn demo-preset-btn" data-time="22" data-start="20" data-end="45">BOOST (22s)</button>
                    <button type="button" class="demo-hud-btn demo-preset-btn" data-time="45" data-start="45" data-end="47">APOGEE (45s)</button>
                    <button type="button" class="demo-hud-btn demo-preset-btn" data-time="75" data-start="45" data-end="115">DROGUE C3</button>
                    <button type="button" class="demo-hud-btn demo-preset-btn" data-time="140" data-start="115" data-end="200">MAIN C4</button>
                    <button type="button" class="demo-hud-btn demo-preset-btn" data-time="205" data-start="200" data-end="240">LANDED</button>
                </div>
            </div>
        `;
        document.body.appendChild(hud);

        // Bind HUD events
        const playBtn = document.getElementById('demoBtnPlay');
        if (playBtn) {
            playBtn.addEventListener('click', () => {
                demoEngine.paused = !demoEngine.paused;
                playBtn.textContent = demoEngine.paused ? '▶' : '⏸';
                playBtn.classList.toggle('paused', demoEngine.paused);
            });
        }

        const slider = document.getElementById('demoHudSlider');
        if (slider) {
            slider.addEventListener('input', (e) => {
                jumpToSimTime(parseFloat(e.target.value));
            });
        }

        hud.querySelectorAll('.demo-preset-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                jumpToSimTime(parseFloat(btn.dataset.time || 0));
            });
        });

        const speedBtn = document.getElementById('demoBtnSpeed');
        const speeds = [1, 2, 5, 10];
        if (speedBtn) {
            speedBtn.addEventListener('click', () => {
                const nextIdx = (speeds.indexOf(demoEngine.speed) + 1) % speeds.length;
                demoEngine.speed = speeds[nextIdx];
                speedBtn.textContent = `${demoEngine.speed}x`;
                speedBtn.classList.toggle('active', demoEngine.speed > 1);
            });
        }

        const minBtn = document.getElementById('demoBtnMin');
        const bodyWrap = document.getElementById('demoHudBody');
        if (minBtn && bodyWrap) {
            minBtn.addEventListener('click', () => {
                demoEngine.minimized = !demoEngine.minimized;
                hud.classList.toggle('minimized', demoEngine.minimized);
                bodyWrap.style.display = demoEngine.minimized ? 'none' : 'flex';
                minBtn.textContent = demoEngine.minimized ? '▢' : '▼';
            });
        }

        // Draggable HUD functionality
        const hudHeader = hud.querySelector('.demo-hud-header');
        if (hudHeader) {
            hudHeader.style.cursor = 'grab';
            let isDragging = false;
            let startX = 0, startY = 0, startLeft = 0, startTop = 0;

            hudHeader.addEventListener('mousedown', (e) => {
                if (e.target.tagName === 'BUTTON') return;
                isDragging = true;
                hudHeader.style.cursor = 'grabbing';
                startX = e.clientX;
                startY = e.clientY;
                const rect = hud.getBoundingClientRect();
                startLeft = rect.left;
                startTop = rect.top;
                hud.style.bottom = 'auto';
                hud.style.right = 'auto';
                hud.style.left = `${startLeft}px`;
                hud.style.top = `${startTop}px`;
                e.preventDefault();
            });

            window.addEventListener('mousemove', (e) => {
                if (!isDragging) return;
                const dx = e.clientX - startX;
                const dy = e.clientY - startY;
                const maxLeft = window.innerWidth - hud.offsetWidth - 8;
                const maxTop = window.innerHeight - hud.offsetHeight - 8;
                hud.style.left = `${Math.max(8, Math.min(maxLeft, startLeft + dx))}px`;
                hud.style.top = `${Math.max(8, Math.min(maxTop, startTop + dy))}px`;
            });

            window.addEventListener('mouseup', () => {
                if (isDragging) {
                    isDragging = false;
                    hudHeader.style.cursor = 'grab';
                }
            });
        }

        updateDemoHudUI();
    }

    // Add Live / Demo mode switch pill into the header
    function injectHeaderBadge() {
        const brandSec = document.querySelector('.brand-section');
        if (!brandSec) return;

        const tag = document.createElement('a');
        tag.id = 'demoPillBadge';
        if (IS_DEMO) {
            tag.className = 'demo-header-tag';
            tag.textContent = 'DEMO ACTIVE';
            tag.title = 'Running client-side CanSat simulation. Click to switch to Live mode.';
            tag.onclick = (e) => { e.preventDefault(); window.exitDemoMode(); };
        } else {
            tag.className = 'demo-header-tag live-btn';
            tag.textContent = 'LAUNCH DEMO';
            tag.title = 'Click to launch interactive client-side CanSat flight simulation';
            tag.onclick = (e) => { e.preventDefault(); window.enterDemoMode(); };
        }
        brandSec.appendChild(tag);
    }

    // Initialize on DOM load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            mountDemoHud();
            injectHeaderBadge();
        });
    } else {
        mountDemoHud();
        injectHeaderBadge();
    }
})();
