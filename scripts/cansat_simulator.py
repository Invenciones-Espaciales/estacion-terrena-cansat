#!/usr/bin/env python3
"""CanSat CONAE 2026-2027 Telemetry & Command Simulator.

Creates a virtual serial link (PTY) at /tmp/cansat_uart and streams 1 Hz
plain-text telemetry matching official CONAE requirements:
TEAM_ID, MISSION_TIME, PACKET_COUNT, MODE, STATE, ALTITUDE, TEMPERATURE, PRESSURE,
VOLTAGE, CURRENT, GYRO_R, GYRO_P, GYRO_Y, ACCEL_R, ACCEL_P, ACCEL_Y,
GPS_TIME, GPS_ALTITUDE, GPS_LATITUDE, GPS_LONGITUDE, GPS_SATS, CMD_ECHO [,,OPTIONAL_DATA]

Handles bidirectional telecommands (G15, G1, F3, F5, X6, X3):
- CMD,1000,CAL           -> Calibrate altitude to zero
- CMD,1000,ST,<UTC>      -> Set RTC UTC time
- CMD,1000,PC,0          -> Reset persistent packet counter
- CMD,1000,BATT          -> Request battery & solar panel status
- CMD,1000,SIM,<MODE>    -> Enable / disable simulation mode
- CMD,1000,START         -> Mission start / separation trigger
"""

import datetime
import math
import os
import pty
import select
import sys
import time

UART_SYMLINK = "/tmp/cansat_uart"
TEAM_ID = "1000"
FREQUENCY_HZ = 1.0


class CanSatSimulator:
    def __init__(self):
        self.master_fd, self.slave_fd = pty.openpty()
        self.slave_name = os.ttyname(self.slave_fd)

        # Setup symlink for easy access by Ground Station
        try:
            if os.path.exists(UART_SYMLINK) or os.path.islink(UART_SYMLINK):
                os.unlink(UART_SYMLINK)
            os.symlink(self.slave_name, UART_SYMLINK)
            print(f"[SIMULATOR] Created virtual UART: {UART_SYMLINK} -> {self.slave_name}")
        except Exception as e:
            print(f"[SIMULATOR] Symlink warning: {e}. Using raw device: {self.slave_name}")

        self.packet_count = 1
        self.mode = "F"
        self.state = "LAUNCH_PAD"
        self.altitude = 0.0
        self.calibrated_ground_alt = 25.0
        self.voltage = 4.12
        self.current = 0.18
        self.last_cmd_echo = "BOOT_OK"
        self.mission_start_epoch = time.time()
        self.flight_start_epoch = None
        self.sim_phase_time = 0.0

        # GPS Base coordinates (Falda del Cañete / CONAE Space Center)
        self.base_lat = -31.5238
        self.base_lon = -64.4642
        self.base_alt = 750.0

    def process_incoming_commands(self):
        """Check if Ground Station sent any commands over the UART."""
        while True:
            r, _, _ = select.select([self.master_fd], [], [], 0)
            if not r:
                break
            try:
                raw = os.read(self.master_fd, 512).decode("utf-8", errors="replace")
                lines = raw.strip().split("\n")
                for line in lines:
                    cmd = line.strip().strip("\r")
                    if not cmd:
                        continue
                    print(f"[SIMULATOR RX CMD] {cmd}")
                    self.execute_command(cmd)
            except Exception as e:
                print(f"[SIMULATOR] Error reading command: {e}")
                break

    def execute_command(self, cmd_str: str):
        tokens = [t.strip() for t in cmd_str.split(",")]
        # Standard CanSat command format: CMD,TEAM_ID,COMMAND_NAME[,ARG]
        if len(tokens) >= 3 and tokens[0].upper() == "CMD":
            cmd_name = tokens[2].upper()
            self.last_cmd_echo = cmd_name

            if cmd_name in ("CAL", "CX"):
                # G1, F5: Calibrate altitude to zero
                self.altitude = 0.0
                print("[SIMULATOR] Altitude calibrated to 0.0 m (G1, F5)")
            elif cmd_name == "PC":
                # Reset packet count
                self.packet_count = 0
                print("[SIMULATOR] Packet count reset to 0")
            elif cmd_name == "ST":
                # F3, F2: Synchronize UTC Time
                print(f"[SIMULATOR] UTC Time synchronized: {tokens[3] if len(tokens)>3 else 'GPS'}")
            elif cmd_name == "BATT":
                # X6: Query battery & solar
                print(f"[SIMULATOR] Battery report requested: {self.voltage:.2f}V, {self.current:.2f}A")
            elif cmd_name == "SIM":
                sub = tokens[3].upper() if len(tokens) > 3 else "ENABLE"
                if sub == "ENABLE":
                    self.mode = "S"
                elif sub == "DISABLE":
                    self.mode = "F"
                print(f"[SIMULATOR] Mode changed to: {self.mode}")
            elif cmd_name == "START":
                # X3: Mission start separation
                self.state = "DESCENT"
                print("[SIMULATOR] Mission start triggered!")

    def update_physics(self, dt: float):
        """Update CanSat flight dynamics profile."""
        self.sim_phase_time += dt

        # Flight state machine timeline
        if self.state == "LAUNCH_PAD":
            self.altitude = 0.0
            self.current = 0.18 + 0.02 * math.sin(self.sim_phase_time)
            # After 15 seconds on launchpad, initiate ascent
            if self.sim_phase_time > 15.0:
                self.state = "ASCENT"
                self.flight_start_epoch = time.time()
                self.sim_phase_time = 0.0
                print("[SIMULATOR] >>> MOTOR IGNITION & ASCENT <<<")

        elif self.state == "ASCENT":
            # Powered ascent at ~65 m/s up to 1000m apogee
            self.altitude += 65.0 * dt
            self.current = 0.35 + 0.05 * math.sin(self.sim_phase_time * 5)
            if self.altitude >= 1000.0:
                self.altitude = 1000.0
                self.state = "APOGEE"
                self.sim_phase_time = 0.0
                self.last_cmd_echo = "SEPARATION_OK" # X3 Automatic mission start
                print("[SIMULATOR] >>> APOGEE REACHED (1000m) & SEPARATION (X3) <<<")

        elif self.state == "APOGEE":
            # Brief apex pause
            if self.sim_phase_time >= 2.0:
                self.state = "DESCENT"
                self.sim_phase_time = 0.0
                print("[SIMULATOR] >>> DROGUE DESCENT PHASE C3 (15 m/s) <<<")

        elif self.state == "DESCENT":
            # Phase C3: First 20% of descent (1000m down to 800m) at 15 ± 3 m/s
            if self.altitude > 800.0:
                self.altitude -= 15.0 * dt
            # Phase C4: Remaining 80% (800m down to ground) at 5 ± 3 m/s
            else:
                self.altitude -= 5.0 * dt

            self.current = 0.22 + 0.03 * math.sin(self.sim_phase_time)

            if self.altitude <= 0.0:
                self.altitude = 0.0
                self.state = "LANDED"
                self.sim_phase_time = 0.0
                print("[SIMULATOR] >>> TOUCHDOWN & LANDED <<<")

        elif self.state == "LANDED":
            self.altitude = 0.0
            self.current = 0.15

        # Battery slow discharge
        self.voltage = max(3.3, self.voltage - 0.0001)

        # Barometric pressure (hypsometric formula)
        # P = 101.325 * (1 - 2.25577e-5 * h)^5.25588
        h_total = self.calibrated_ground_alt + self.altitude
        self.pressure = 101.325 * math.pow(1.0 - 2.25577e-5 * h_total, 5.25588)

        # Ambient temperature lapse rate: -6.5 °C / 1000m
        self.temperature = 22.0 - (self.altitude * 0.0065)

    def generate_telemetry_line(self) -> str:
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        mission_time = now_utc.strftime("%H:%M:%S")

        # Gyroscope rates (°/s)
        if self.state in ("ASCENT", "DESCENT"):
            gyro_r = 15.0 * math.sin(self.sim_phase_time * 2)
            gyro_p = 8.0 * math.cos(self.sim_phase_time * 1.5)
            gyro_y = 25.0 * math.sin(self.sim_phase_time * 0.8)
        else:
            gyro_r = 0.1
            gyro_p = 0.1
            gyro_y = 0.0

        # Accelerometer (m/s²)
        if self.state == "ASCENT":
            accel_r = 0.5
            accel_p = 0.3
            accel_y = 28.5  # Thrust acceleration (~3G)
        elif self.state == "DESCENT":
            accel_r = 0.4 * math.sin(self.sim_phase_time)
            accel_p = 0.3 * math.cos(self.sim_phase_time)
            accel_y = 9.81
        else:
            accel_r = 0.02
            accel_p = 0.01
            accel_y = 9.81

        # GPS Drift simulation with wind
        wind_drift_km = (self.sim_phase_time * 0.005) if self.state in ("ASCENT", "DESCENT") else 0.0
        lat = self.base_lat + (wind_drift_km * 0.009)
        lon = self.base_lon + (wind_drift_km * 0.009)
        gps_alt = self.base_alt + self.altitude
        gps_sats = 12 if self.state != "LAUNCH_PAD" else 10

        # Build official 22-field CSV format
        fields = [
            TEAM_ID,
            mission_time,
            str(self.packet_count),
            self.mode,
            self.state,
            f"{self.altitude:.1f}",
            f"{self.temperature:.1f}",
            f"{self.pressure:.1f}",
            f"{self.voltage:.2f}",
            f"{self.current:.2f}",
            f"{gyro_r:.1f}",
            f"{gyro_p:.1f}",
            f"{gyro_y:.1f}",
            f"{accel_r:.2f}",
            f"{accel_p:.2f}",
            f"{accel_y:.2f}",
            mission_time,
            f"{gps_alt:.1f}",
            f"{lat:.4f}",
            f"{lon:.4f}",
            str(gps_sats),
            self.last_cmd_echo,
        ]

        # Optional payload sensor: solar bus and internal temperature
        solar_v = 4.85 if self.state in ("ASCENT", "DESCENT", "APOGEE") else 0.05
        optional = f"SOLAR_V:{solar_v:.2f},PWR_STATUS:OK"

        return ",".join(fields) + ",," + optional

    def run(self):
        print(f"[SIMULATOR] CanSat telemetry streaming started at {FREQUENCY_HZ} Hz...")
        last_tick = time.time()

        try:
            while True:
                now = time.time()
                dt = now - last_tick
                last_tick = now

                self.process_incoming_commands()
                self.update_physics(dt)

                line = self.generate_telemetry_line() + "\r\n"
                try:
                    os.write(self.master_fd, line.encode("utf-8"))
                except Exception as e:
                    print(f"[SIMULATOR] Write error: {e}")

                self.packet_count += 1
                time.sleep(1.0 / FREQUENCY_HZ)
        except KeyboardInterrupt:
            print("\n[SIMULATOR] Stopped by user.")
        finally:
            try:
                os.close(self.master_fd)
                os.close(self.slave_fd)
                if os.path.islink(UART_SYMLINK):
                    os.unlink(UART_SYMLINK)
            except Exception:
                pass


if __name__ == "__main__":
    sim = CanSatSimulator()
    sim.run()
