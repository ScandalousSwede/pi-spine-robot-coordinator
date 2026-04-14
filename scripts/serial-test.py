#!/usr/bin/env python3
"""
Pi Spine — Serial Connectivity Test
Sends a command to an ESP32 over serial and prints the response.

Usage:
    python3 serial-test.py CONNECT
    python3 serial-test.py CONNECT --port /dev/ttyUSB1
    python3 serial-test.py "jogJ A5 B0 C0 D0 E0 F0 G20 H10"
"""

import serial
import argparse
import time
import sys
import json
from datetime import datetime

DEFAULT_PORT = "/dev/ttyUSB0"
BAUD_RATE = 57600
READ_TIMEOUT = 3.0  # seconds


def send_command(port: str, command: str, timeout: float = READ_TIMEOUT) -> list[str]:
    """Send a command over serial and collect all response lines until END or timeout."""
    responses = []
    
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=timeout)
        time.sleep(0.1)  # Let connection settle
        
        # Clear any stale data
        ser.reset_input_buffer()
        
        # Send command
        cmd_bytes = (command.strip() + "\n").encode()
        ser.write(cmd_bytes)
        
        timestamp = datetime.now().isoformat()
        print(f"[{timestamp}] TX → {command.strip()}")
        
        # Read responses until END or timeout
        start = time.time()
        while (time.time() - start) < timeout:
            if ser.in_waiting > 0:
                line = ser.readline().decode(errors="replace").strip()
                if line:
                    timestamp = datetime.now().isoformat()
                    responses.append(line)
                    print(f"[{timestamp}] RX ← {line}")
                    
                    if line == "END":
                        break
            else:
                time.sleep(0.01)
        
        ser.close()
        
    except serial.SerialException as e:
        print(f"[ERROR] Serial error on {port}: {e}")
        sys.exit(1)
    
    if not responses:
        print(f"[WARN] No response within {timeout}s")
    
    return responses


def main():
    parser = argparse.ArgumentParser(description="Pi Spine — Serial Test")
    parser.add_argument("command", help="Command to send (e.g., CONNECT, stop, Home)")
    parser.add_argument("--port", default=DEFAULT_PORT, help=f"Serial port (default: {DEFAULT_PORT})")
    parser.add_argument("--timeout", type=float, default=READ_TIMEOUT, help=f"Read timeout in seconds (default: {READ_TIMEOUT})")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    
    responses = send_command(args.port, args.command, args.timeout)
    
    if args.json:
        result = {
            "port": args.port,
            "command": args.command,
            "responses": responses,
            "timestamp": datetime.now().isoformat(),
            "success": len(responses) > 0
        }
        print(json.dumps(result, indent=2))
    
    # Exit code: 0 if got response, 1 if no response
    sys.exit(0 if responses else 1)


if __name__ == "__main__":
    main()
