# Interactive Client-Side Demo Mode

The **CanSat CONAE Ground Station** includes a pure client-side simulation engine ([`frontend/js/demo_mode.js`](../frontend/js/demo_mode.js)) that allows the entire dashboard to run without a Python backend or physical RF transceiver—ideal for **GitHub Pages** hosting, operator training, and UI verification.

---

## 1. Activation & Detection

`initCanSatDemoEngine()` runs on page load and determines whether to activate Demo Mode using the following priority order:

1. **Explicit Disable (`?demo=0`, `?demo=false`, `?mode=live`):** Clears `sessionStorage.cansat_demo_mode` and connects to the live FastAPI WebSocket backend.
2. **Explicit Enable (`?demo=1`, `?demo=true`, `?mode=demo`, `#demo`):** Sets `sessionStorage.cansat_demo_mode = '1'` and activates Demo Mode across page navigations.
3. **Static Hosting Auto-Detection:** Automatically activates when `window.location.protocol === 'file:'` or when `window.location.hostname` matches:
   - `*.github.io` (GitHub Pages)
   - `*.pages.dev` (Cloudflare Pages)
   - `*.netlify.app` (Netlify)
   - `*.vercel.app` (Vercel)

---

## 2. How It Works Under the Hood

When Demo Mode is active, `demo_mode.js` intercepts browser networking APIs so the dashboard operates identically to a live session:

- **WebSocket Mocking:** Intercepts WebSocket connections and dispatches live 1 Hz telemetry frames directly to the dashboard's message handler.
- **`fetch('/api/command')` Interception:** Parses telecommands (`CAL`, `ST`, `PC`, `BATT`, `SIM`, `START`, etc.) and updates the simulated flight state and `CMD_ECHO` field in real time.
- **`fetch('/api/export/csv')` Interception:** Generates and triggers an instantaneous client-side download of `Flight_1000.csv` containing the simulated 22-field CONAE ASCII telemetry history.

---

## 3. Simulated 240-Second Flight Profile

The simulator generates a complete 240-second mission matching the official **22-field CONAE Plain-Text CSV** format at 1 Hz:

| Phase | State | Key Characteristics |
| :--- | :--- | :--- |
| **Pre-Launch** | `LAUNCH_PAD` | Stationary on pad, baseline barometric pressure & temperature, GPS lock. |
| **Ascent** | `ASCENT` | High vertical acceleration, rising barometric & GPS altitude, increasing velocity. |
| **Apogee** | `APOGEE` | Peak altitude (~700–1000 m), near-zero vertical velocity, deployment trigger. |
| **Drogue Descent** | `DESCENT` / `PROBE_RELEASE` | Descent velocity regulated around **C3** ($15 \pm 3\text{ m/s}$). |
| **Main Descent** | `PAYLOAD_RELEASE` | Descent velocity regulated around **C4** ($5 \pm 3\text{ m/s}$). |
| **Touchdown** | `LANDED` | Zero vertical velocity, final GPS coordinates for recovery. |

---

## 4. Draggable Demo Controller HUD

In Demo Mode, a floating, draggable **Demo Controller HUD** appears on screen, providing:

- **Play / Pause** toggle for the 1 Hz telemetry clock.
- **Playback Speed** selector (`1x`, `2x`, `5x`, `10x`).
- **Timeline Scrubber** to jump to any second in the 240-second flight.
- **Phase Jump Buttons** to immediately test `LAUNCH_PAD`, `ASCENT`, `APOGEE`, `DESCENT`, or `LANDED`.
