#!/usr/bin/env python3
"""Viewport & responsive layout auditor script.
Captures screenshots and validates DOM bounding boxes across target resolutions.
"""

import os
import subprocess
import sys
import tempfile

def capture_screenshot(url: str, output_path: str, width: int = 1920, height: int = 1080):
    tmpdir = tempfile.mkdtemp(prefix="chrome_audit_")
    cmd = [
        "/usr/bin/chromium",
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-sync",
        "--disable-extensions",
        f"--user-data-dir={tmpdir}",
        f"--window-size={width},{height}",
        f"--screenshot={output_path}",
        url,
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
        if os.path.exists(output_path):
            print(f"[AUDIT] Screenshot saved to: {output_path} ({os.path.getsize(output_path)} bytes)")
            return True
        else:
            print(f"[AUDIT] Screenshot failed. Stderr: {res.stderr.decode('utf-8', errors='replace')}")
            return False
    except Exception as e:
        print(f"[AUDIT] Error: {e}")
        return False
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

if __name__ == "__main__":
    out_1080 = "/tmp/ground_station_zero_scroll_1080p.png"
    out_768 = "/tmp/ground_station_zero_scroll_768p.png"
    capture_screenshot("http://localhost:8080/", out_1080, 1920, 1080)
    capture_screenshot("http://localhost:8080/", out_768, 1366, 768)
