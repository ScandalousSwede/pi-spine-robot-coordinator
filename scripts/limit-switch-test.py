#!/usr/bin/env python3
"""
Pi Spine — Limit Switch Test
Reads IO input states to determine limit switch wiring polarity.

The MiKoBots firmware monitors inputs and sends "Input {channel} {0|1}" messages
when an input changes state. This script monitors those messages to determine
whether limit switches are active-high or active-low.

Usage:
    python3 limit-switch-test.py --port /dev/ttyUSB0
    
Instructions:
    1. Run this script
    2. Manually press each limit switch one at a time
    3. Script will report which input channel changed and its polarity
    4. Results saved to config/limit-switch-map.json
"""

import serial
import time
import json
import argparse
import sys
from datetime import datetime

BAUD_RATE = 57600


def monitor_inputs(port: str, duration: float = 60.0):
    """Monitor serial for Input state change messages."""
    print(f"Monitoring {port} for limit switch events...")
    print(f"Press each limit switch one at a time.")
    print(f"Will run for {duration} seconds. Press Ctrl+C to stop early.\n")
    
    events = []
    
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=0.1)
        time.sleep(0.5)
        ser.reset_input_buffer()
        
        start = time.time()
        while (time.time() - start) < duration:
            if ser.in_waiting > 0:
                line = ser.readline().decode(errors="replace").strip()
                if line.startswith("Input "):
                    # Parse "Input {channel} {value}"
                    parts = line.split()
                    if len(parts) == 3:
                        channel = int(parts[1])
                        value = int(parts[2])
                        timestamp = datetime.now().isoformat()
                        
                        state = "TRIGGERED (HIGH)" if value == 1 else "RELEASED (LOW)"
                        print(f"  [{timestamp}] Channel {channel}: {state}")
                        
                        events.append({
                            "timestamp": timestamp,
                            "channel": channel,
                            "value": value,
                            "elapsed": round(time.time() - start, 2)
                        })
                elif line:
                    # Print other messages for context
                    print(f"  [other] {line}")
        
        ser.close()
        
    except KeyboardInterrupt:
        print("\nStopped by user.")
        ser.close()
    except serial.SerialException as e:
        print(f"[ERROR] Serial error: {e}")
        sys.exit(1)
    
    return events


def analyze_events(events: list[dict]) -> dict:
    """Analyze limit switch events to determine polarity per channel."""
    channels = {}
    
    for event in events:
        ch = event["channel"]
        if ch not in channels:
            channels[ch] = {"triggers": [], "releases": []}
        
        if event["value"] == 1:
            channels[ch]["triggers"].append(event["timestamp"])
        else:
            channels[ch]["releases"].append(event["timestamp"])
    
    analysis = {}
    for ch, data in sorted(channels.items()):
        trigger_count = len(data["triggers"])
        release_count = len(data["releases"])
        
        # If we see trigger then release, switch is normally-open (active-high)
        # If we see release then trigger, switch is normally-closed (active-low / inverted)
        polarity = "unknown"
        if trigger_count > 0 and release_count > 0:
            polarity = "active-high (normally open)"
        elif trigger_count > 0:
            polarity = "active-high (no release detected — held?)"
        elif release_count > 0:
            polarity = "active-low (normally closed) — MAY BE INVERTED"
        
        analysis[f"channel_{ch}"] = {
            "trigger_count": trigger_count,
            "release_count": release_count,
            "polarity": polarity
        }
    
    return analysis


def main():
    parser = argparse.ArgumentParser(description="Pi Spine — Limit Switch Test")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Motion ESP32 serial port")
    parser.add_argument("--duration", type=float, default=60.0, help="Monitoring duration in seconds")
    args = parser.parse_args()
    
    print("Pi Spine — Limit Switch Polarity Test")
    print("=" * 40)
    
    events = monitor_inputs(args.port, args.duration)
    
    if not events:
        print("\nNo limit switch events detected.")
        print("Possible causes:")
        print("  - IO input pins not configured in firmware (need Set_io_pin first)")
        print("  - Switches not wired to the expected pins")
        print("  - Switches need to be physically pressed harder")
        return
    
    print(f"\n{'=' * 40}")
    print(f"Captured {len(events)} events across {len(set(e['channel'] for e in events))} channels")
    
    analysis = analyze_events(events)
    for ch, data in analysis.items():
        print(f"\n  {ch}:")
        print(f"    Triggers: {data['trigger_count']}")
        print(f"    Releases: {data['release_count']}")
        print(f"    Polarity: {data['polarity']}")
    
    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "events": events,
        "analysis": analysis
    }
    
    outpath = "limit-switch-map.json"
    with open(outpath, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {outpath}")


if __name__ == "__main__":
    main()
