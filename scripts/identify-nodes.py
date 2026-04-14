#!/usr/bin/env python3
"""
Pi Spine — Node Identification
Determines which /dev/ttyUSB port connects to which ESP32 node.

Sends CONNECT to each detected serial port and classifies based on response:
- "ROBOT_CONNECTED" → Motion ESP32
- "IO_CONNECTED"    → IO Box ESP32

Usage:
    python3 identify-nodes.py
"""

import serial
import glob
import time
import json
import sys
from datetime import datetime

BAUD_RATE = 57600
TIMEOUT = 3.0


def probe_port(port: str) -> dict:
    """Send CONNECT to a serial port and classify the response."""
    result = {
        "port": port,
        "type": "unknown",
        "response": None,
        "error": None
    }
    
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=TIMEOUT)
        time.sleep(0.5)  # ESP32 may need time after connection
        
        ser.reset_input_buffer()
        ser.write(b"CONNECT\n")
        
        start = time.time()
        while (time.time() - start) < TIMEOUT:
            if ser.in_waiting > 0:
                line = ser.readline().decode(errors="replace").strip()
                if line:
                    result["response"] = line
                    
                    if "ROBOT_CONNECTED" in line:
                        result["type"] = "motion"
                        break
                    elif "IO_CONNECTED" in line:
                        result["type"] = "io"
                        break
            time.sleep(0.01)
        
        ser.close()
        
    except serial.SerialException as e:
        result["error"] = str(e)
    
    return result


def main():
    print("Pi Spine — Node Identification")
    print("=" * 40)
    print()
    
    # Find all serial ports
    ports = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
    
    if not ports:
        print("[ERROR] No serial devices found.")
        print("  - Are both ESPs plugged in via USB?")
        print("  - Check: ls /dev/ttyUSB* /dev/ttyACM*")
        print("  - If permission denied: sudo usermod -a -G dialout $USER && logout")
        sys.exit(1)
    
    print(f"Found {len(ports)} serial device(s): {', '.join(ports)}")
    print()
    
    # Probe each port
    results = []
    for port in ports:
        print(f"Probing {port}...")
        result = probe_port(port)
        results.append(result)
        
        if result["error"]:
            print(f"  ✗ Error: {result['error']}")
        elif result["type"] == "unknown":
            print(f"  ? No recognized response (got: {result['response']})")
        else:
            print(f"  ✓ {result['type'].upper()} node — response: {result['response']}")
        print()
    
    # Summary
    print("=" * 40)
    print("Node Map:")
    
    node_map = {}
    for r in results:
        if r["type"] != "unknown":
            node_map[r["type"]] = r["port"]
            print(f"  {r['type']:>8} → {r['port']}")
    
    if "motion" not in node_map:
        print("  [WARN] Motion ESP32 not found!")
    if "io" not in node_map:
        print("  [INFO] IO Box ESP32 not found (may not have IO firmware)")
    
    # Save node map
    output = {
        "timestamp": datetime.now().isoformat(),
        "nodes": results,
        "port_map": node_map
    }
    
    outpath = "/home/ethan/pi-spine/config/node-map.json"
    try:
        with open(outpath, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nSaved to {outpath}")
    except FileNotFoundError:
        # Fallback to current directory
        outpath = "node-map.json"
        with open(outpath, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nSaved to {outpath}")


if __name__ == "__main__":
    main()
