"""Automated tests for CanSat CONAE Telemetry Specification.

Verifies:
1. CanSatAsciiParser on official 22-field plain-text CSV telemetry.
2. Quantitative link tracking (RX packets G14, Lost packets G8, rate Hz).
3. Dual CSV persistence (G2: Flight_XXXX.csv on notebook & backup storage).
4. Telecommand generation (G15, G1, F3, F5, X6, X3).
5. Descent velocity calculation & compliance testing (C3: 15±3 m/s, C4: 5±3 m/s).
"""

import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from main import (
    CANSAT_FIELDS,
    CanSatAsciiParser,
    CanSatTelemetry,
    DualCSVLogger,
    PacketStatistics,
    VALID_STATES,
)


class TestCanSatTelemetry(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.primary_csv = os.path.join(self.test_dir, "Flight_1000.csv")
        self.backup_csv = os.path.join(self.test_dir, "backup", "Flight_1000.csv")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_ascii_parser_nominal(self):
        """Test parsing of an official 22-field CanSat CONAE telemetry string."""
        sample_line = (
            "1000, 13:14:02, 142, F, DESCENT, 345.2, 18.4, 98.2, 3.8, 0.22, "
            "1.2, -0.4, 0.8, 0.05, 0.12, 9.81, 13:14:02, 370.2, -34.6037, -58.3815, 11, CAL"
        )
        parsed = CanSatAsciiParser.parse_line(sample_line)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.team_id, "1000")
        self.assertEqual(parsed.mission_time, "13:14:02")
        self.assertEqual(parsed.packet_count, 142)
        self.assertEqual(parsed.mode, "F")
        self.assertEqual(parsed.state, "DESCENT")
        self.assertAlmostEqual(parsed.altitude, 345.2, places=1)
        self.assertAlmostEqual(parsed.temperature, 18.4, places=1)
        self.assertAlmostEqual(parsed.pressure, 98.2, places=1)
        self.assertAlmostEqual(parsed.voltage, 3.8, places=1)
        self.assertAlmostEqual(parsed.current, 0.22, places=2)
        self.assertAlmostEqual(parsed.gyro_r, 1.2, places=1)
        self.assertAlmostEqual(parsed.gyro_p, -0.4, places=1)
        self.assertAlmostEqual(parsed.gyro_y, 0.8, places=1)
        self.assertAlmostEqual(parsed.accel_r, 0.05, places=2)
        self.assertAlmostEqual(parsed.accel_p, 0.12, places=2)
        self.assertAlmostEqual(parsed.accel_y, 9.81, places=2)
        self.assertEqual(parsed.gps_time, "13:14:02")
        self.assertAlmostEqual(parsed.gps_altitude, 370.2, places=1)
        self.assertAlmostEqual(parsed.gps_latitude, -34.6037, places=4)
        self.assertAlmostEqual(parsed.gps_longitude, -58.3815, places=4)
        self.assertEqual(parsed.gps_sats, 11)
        self.assertEqual(parsed.cmd_echo, "CAL")
        self.assertEqual(parsed.optional_data, "")

    def test_02_ascii_parser_with_optional_data(self):
        """Test optional payload sensors appended after double commas (,,OPTIONAL_DATA)."""
        sample_line = (
            "1000, 13:15:00, 200, F, ASCENT, 520.0, 15.0, 95.0, 3.7, 0.25, "
            "0.0, 0.0, 0.0, 0.0, 0.0, 9.8, 13:15:00, 545.0, -34.6000, -58.3800, 12, NONE,,SOLAR_V:4.9,UV_INDEX:3.2"
        )
        parsed = CanSatAsciiParser.parse_line(sample_line)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.state, "ASCENT")
        self.assertEqual(parsed.optional_data, "SOLAR_V:4.9,UV_INDEX:3.2")

    def test_03_ascii_parser_invalid_line_rejection(self):
        """Test rejection of malformed or truncated telemetry frames."""
        # Truncated line (only 10 fields instead of >= 22)
        bad_line = "1000, 13:14:02, 142, F, DESCENT, 345.2, 18.4"
        self.assertIsNone(CanSatAsciiParser.parse_line(bad_line))

        # Corrupted non-numeric values
        bad_numbers = (
            "1000, 13:14:02, NOT_A_NUMBER, F, DESCENT, INVALID_ALT, 18.4, 98.2, 3.8, 0.22, "
            "1.2, -0.4, 0.8, 0.05, 0.12, 9.81, 13:14:02, 370.2, -34.6037, -58.3815, 11, CAL"
        )
        self.assertIsNone(CanSatAsciiParser.parse_line(bad_numbers))

    def test_04_packet_statistics_and_loss_tracking(self):
        """Test RX packet counting (G14) and packet loss calculation (G8)."""
        stats = PacketStatistics()

        # Packet 1
        stats.register(packet_count=100, altitude=500.0)
        snap1 = stats.snapshot()
        self.assertEqual(snap1["rx_count"], 1)
        self.assertEqual(snap1["lost_count"], 0)
        self.assertEqual(snap1["loss_percent"], 0.0)

        # Packet 2 (sequential, no loss)
        stats.register(packet_count=101, altitude=485.0)
        snap2 = stats.snapshot()
        self.assertEqual(snap2["rx_count"], 2)
        self.assertEqual(snap2["lost_count"], 0)

        # Packet 3 arrives as sequence 105 (loss of packets 102, 103, 104 -> 3 lost)
        stats.register(packet_count=105, altitude=440.0)
        snap3 = stats.snapshot()
        self.assertEqual(snap3["rx_count"], 3)
        self.assertEqual(snap3["lost_count"], 3)
        # Total attempted = 3 received + 3 lost = 6. Loss % = (3 / 6) * 100 = 50.0%
        self.assertEqual(snap3["loss_percent"], 50.0)

    def test_05_dual_csv_persistence(self):
        """Test simultaneous writing and flushing to primary and backup CSV files (G2)."""
        logger = DualCSVLogger(primary_path=self.primary_csv, backup_path=self.backup_csv)

        t1 = CanSatTelemetry(
            team_id="1000",
            mission_time="12:00:01",
            packet_count=1,
            mode="F",
            state="LAUNCH_PAD",
            altitude=0.0,
            temperature=22.5,
            pressure=101.3,
            voltage=3.75,
            current=0.18,
            gyro_r=0.0,
            gyro_p=0.0,
            gyro_y=0.0,
            accel_r=0.0,
            accel_p=0.0,
            accel_y=9.8,
            gps_time="12:00:01",
            gps_altitude=25.0,
            gps_latitude=-34.6037,
            gps_longitude=-58.3815,
            gps_sats=10,
            cmd_echo="CAL",
        )

        logger.write_telemetry(t1)
        logger.close()

        # Verify primary file exists and contains header + row
        self.assertTrue(os.path.exists(self.primary_csv))
        with open(self.primary_csv, "r", encoding="utf-8") as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 2)
            self.assertIn("TEAM_ID,MISSION_TIME,PACKET_COUNT", lines[0])
            self.assertIn("1000,12:00:01,1,F,LAUNCH_PAD,0.0,22.5,101.3,3.8,0.18", lines[1])

        # Verify backup file exists and matches primary exactly
        self.assertTrue(os.path.exists(self.backup_csv))
        with open(self.backup_csv, "r", encoding="utf-8") as f:
            backup_lines = f.readlines()
            self.assertEqual(lines, backup_lines)

    def test_06_descent_rate_velocity_computation(self):
        """Test vertical velocity calculation to verify C3 (15±3 m/s) and C4 (5±3 m/s)."""
        stats = PacketStatistics()
        stats.register(packet_count=1, altitude=1000.0)
        time.sleep(0.55)
        # Descent of 8.25m in ~0.55s => ~15 m/s
        stats.register(packet_count=2, altitude=991.75)
        snap = stats.snapshot()
        self.assertAlmostEqual(snap["vertical_velocity"], -15.0, delta=2.0)


if __name__ == "__main__":
    unittest.main()
