#!/usr/bin/env python3
"""
Pi Spine — GPIO Sweep for Pin Mapping
Systematically toggles ESP32 GPIO pins to identify DIR/PUL/LIMIT assignments.

WARNING: Run this ONLY with Ethan present. Motors may move unexpectedly.

How it works:
1. Sends firmware Set_motor_pin commands to reassign pin pairs
2. Sends small jog commands to test each assignment
3. Ethan observes which motor responds (audio/visual/touch)
4. Builds verified gpio-map.json

Usage:
    python3 gpio-sweep.py --port /dev/ttyUSB0
    python3 gpio-sweep.py --port /dev/ttyUSB0 --interactive
"""

import serial
import time
import json
import argparse
import sys
from datetime import datetime

BAUD_RATE = 57600
TIMEOUT = 5.0

# ESP32 usable GPIO pins (avoiding strapping pins, flash pins, input-only pins)
# Adjust based on your specific ESP32 board
ESP32_GPIO_CANDIDATES = [
    2, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33
]

# Known joint names
JOINTS = ["J1", "J2", "J3", "J4", "J5", "J6"]


def send_and_wait(ser: serial.Serial, command: str, timeout: float = TIMEOUT) -> list[str]:
    """Send command and collect responses until END or timeout."""
    ser.reset_input_buffer()
    ser.write((command.strip() + "\n").encode())
    
    responses = []
    start = time.time()
    while (time.time() - start) < timeout:
        if ser.in_waiting > 0:
            line = ser.readline().decode(errors="replace").strip()
            if line:
                responses.append(line)
                if line == "END":
                    break
        time.sleep(0.01)
    
    return responses


def connect(port: str) -> serial.Serial:
    """Open serial connection and verify ESP32 responds."""
    ser = serial.Serial(port, BAUD_RATE, timeout=TIMEOUT)
    time.sleep(1.0)
    
    responses = send_and_wait(ser, "CONNECT")
    if not any("ROBOT_CONNECTED" in r for r in responses):
        print(f"[ERROR] ESP32 did not respond with ROBOT_CONNECTED")
        print(f"  Got: {responses}")
        ser.close()
        sys.exit(1)
    
    print("[OK] Connected to Motion ESP32")
    return ser


def read_current_gpio_from_ethan() -> dict:
    """Interactive: ask Ethan for known GPIO assignments."""
    print("\n" + "=" * 50)
    print("KNOWN GPIO MAPPING — Enter what you know")
    print("Enter GPIO pin numbers, or 'x' if unknown")
    print("=" * 50)
    
    known = {}
    
    for joint in JOINTS:
        dir_pin = input(f"  {joint} DIR pin [x if unknown]: ").strip()
        pul_pin = input(f"  {joint} PUL/STEP pin [x if unknown]: ").strip()
        
        entry = {"dir": None, "pul": None, "limit": None, "verified": False}
        
        if dir_pin.lower() != "x":
            entry["dir"] = int(dir_pin)
        if pul_pin.lower() != "x":
            entry["pul"] = int(pul_pin)
        
        known[joint] = entry
        print()
    
    return known


def test_single_joint_jog(ser: serial.Serial, joint_index: int, delta: float = 2.0, speed: int = 20, accel: int = 10) -> list[str]:
    """Send a small jog command for a single joint and return responses."""
    # Build jogJ command: jogJ A{j1} B{j2} ... F{j6} G{speed} H{accel}
    # Only the target joint gets a nonzero delta
    alphabet = "ABCDEF"
    parts = ["jogJ"]
    for i in range(6):
        val = delta if i == joint_index else 0
        parts.append(f"{alphabet[i]}{val}")
    parts.append(f"G{speed}")
    parts.append(f"H{accel}")
    
    command = " ".join(parts)
    print(f"  Sending: {command}")
    
    responses = send_and_wait(ser, command, timeout=10.0)
    return responses


def interactive_sweep(ser: serial.Serial, known_map: dict):
    """Interactive GPIO mapping session with Ethan."""
    print("\n" + "=" * 50)
    print("INTERACTIVE GPIO SWEEP")
    print("For each joint, we'll send a small jog command.")
    print("Ethan: observe which motor responds.")
    print("Type the joint that moved, or 'none' if nothing happened.")
    print("Type 'stop' to send emergency stop.")
    print("Type 'quit' to save and exit.")
    print("=" * 50)
    
    verified_map = dict(known_map)
    
    for joint_idx, joint_name in enumerate(JOINTS):
        if verified_map.get(joint_name, {}).get("verified"):
            print(f"\n[SKIP] {joint_name} already verified")
            continue
        
        print(f"\n--- Testing {joint_name} (joint index {joint_idx}) ---")
        print(f"  Sending 2° jog on {joint_name} axis...")
        
        input("  Press ENTER when ready (Ethan should be watching)...")
        
        responses = test_single_joint_jog(ser, joint_idx, delta=2.0)
        
        for r in responses:
            print(f"    ESP: {r}")
        
        result = input(f"  Which motor moved? [{joint_name}/other joint/none/stop/quit]: ").strip().lower()
        
        if result == "stop":
            send_and_wait(ser, "stop")
            print("  *** STOP SENT ***")
            result = input("  Continue? [y/n]: ").strip().lower()
            if result != "y":
                break
            continue
        
        if result == "quit":
            break
        
        if result == joint_name.lower() or result == "":
            print(f"  ✓ {joint_name} confirmed — firmware mapping correct for this joint")
            if joint_name not in verified_map:
                verified_map[joint_name] = {}
            verified_map[joint_name]["verified"] = True
            verified_map[joint_name]["firmware_index"] = joint_idx
        elif result == "none":
            print(f"  ✗ {joint_name} — no movement detected. Pin mapping likely wrong.")
            if joint_name not in verified_map:
                verified_map[joint_name] = {}
            verified_map[joint_name]["verified"] = False
            verified_map[joint_name]["notes"] = "no movement on jog test"
        else:
            print(f"  ⚠ {joint_name} command moved {result.upper()} instead — pins swapped!")
            if joint_name not in verified_map:
                verified_map[joint_name] = {}
            verified_map[joint_name]["verified"] = False
            verified_map[joint_name]["notes"] = f"command for {joint_name} moved {result.upper()}"
    
    return verified_map


def save_map(gpio_map: dict, path: str = None):
    """Save GPIO map to JSON."""
    if path is None:
        path = "/home/ethan/pi-spine/config/gpio-map.json"
    
    output = {
        "timestamp": datetime.now().isoformat(),
        "robot": "MiKoBots 6-DOF",
        "firmware_version": "1.22",
        "joints": gpio_map,
        "notes": "Generated by gpio-sweep.py. Verify all entries before flashing firmware."
    }
    
    try:
        with open(path, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nGPIO map saved to {path}")
    except FileNotFoundError:
        fallback = "gpio-map.json"
        with open(fallback, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nGPIO map saved to {fallback}")


def main():
    parser = argparse.ArgumentParser(description="Pi Spine — GPIO Sweep")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Motion ESP32 serial port")
    parser.add_argument("--interactive", action="store_true", help="Run interactive mapping with Ethan")
    parser.add_argument("--test-joint", type=int, help="Test a single joint index (0-5)")
    args = parser.parse_args()
    
    print("Pi Spine — GPIO Sweep")
    print("⚠  WARNING: Motors may move. Ethan must be present.")
    print()
    
    ser = connect(args.port)
    
    if args.test_joint is not None:
        # Quick single joint test
        print(f"\nTesting joint index {args.test_joint} ({JOINTS[args.test_joint]})...")
        input("Press ENTER when ready...")
        responses = test_single_joint_jog(ser, args.test_joint)
        for r in responses:
            print(f"  ESP: {r}")
    
    elif args.interactive:
        known = read_current_gpio_from_ethan()
        result = interactive_sweep(ser, known)
        save_map(result)
    
    else:
        print("Run with --interactive for guided mapping session")
        print("Run with --test-joint N to test a single joint (0-5)")
    
    ser.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
