#!/usr/bin/env python3
"""
Pi Spine — ICL Intent Translator (Phase 4)
Accepts structured ICL intents (JSON) and translates them to ESP32 firmware commands.

This is the core of the Spine — the boundary between symbolic reasoning and
deterministic control. No natural language enters this layer. Only validated,
unit-aware, frame-aware ICL primitives.

Usage:
    python3 spine-translator.py --motion-port /dev/ttyUSB0 --io-port /dev/ttyUSB1

API (TCP on port 9200):
    POST intent:
    {"verb": "jog", "axis": "X", "delta_mm": 10, "frame": "base", "speed": 50, "accel": 30}
    {"verb": "home"}
    {"verb": "move_joints", "joint_targets": [0, 45, -30, 0, 0, 0], "speed": 80, "accel": 50}
    {"verb": "io_set", "channel": 0, "value": 1}
    {"verb": "stop"}
"""

import serial
import socket
import threading
import json
import time
import argparse
import os
from datetime import datetime
from typing import Optional

BAUD_RATE = 57600
TCP_PORT = 9200
LOG_DIR = os.path.expanduser("~/pi-spine/logs")
CONFIG_DIR = os.path.expanduser("~/pi-spine/config")

# Axis name mapping
AXIS_MAP = {"X": 0, "Y": 1, "Z": 2, "y": 3, "p": 4, "r": 5}
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class SafetyEnvelope:
    """Soft safety bounds — prevents dangerous commands before they reach the ESP."""
    
    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
    
    def _load_config(self, path: str) -> dict:
        """Load safety config or use defaults."""
        defaults = {
            "workspace_bounds": {
                "x_min": -500, "x_max": 500,
                "y_min": -500, "y_max": 500,
                "z_min": 0, "z_max": 500
            },
            "max_jog_delta_mm": 50,
            "max_speed": 100,
            "max_accel": 80,
            "joint_limits": {
                "J1": {"min": -170, "max": 170},
                "J2": {"min": -90, "max": 90},
                "J3": {"min": -90, "max": 90},
                "J4": {"min": -170, "max": 170},
                "J5": {"min": -120, "max": 120},
                "J6": {"min": -360, "max": 360}
            }
        }
        
        if path and os.path.exists(path):
            with open(path) as f:
                loaded = json.load(f)
                defaults.update(loaded)
        
        return defaults
    
    def validate(self, intent: dict) -> tuple[bool, str]:
        """Validate intent against safety bounds. Returns (ok, reason)."""
        verb = intent.get("verb", "")
        
        if verb == "jog":
            delta = abs(intent.get("delta_mm", 0))
            if delta > self.config["max_jog_delta_mm"]:
                return False, f"Jog delta {delta}mm exceeds max {self.config['max_jog_delta_mm']}mm"
        
        if verb in ("jog", "move_joints", "move_cartesian"):
            speed = intent.get("speed", 50)
            accel = intent.get("accel", 30)
            if speed > self.config["max_speed"]:
                return False, f"Speed {speed} exceeds max {self.config['max_speed']}"
            if accel > self.config["max_accel"]:
                return False, f"Accel {accel} exceeds max {self.config['max_accel']}"
        
        if verb == "move_joints":
            targets = intent.get("joint_targets", [])
            limits = self.config["joint_limits"]
            for i, val in enumerate(targets):
                joint = f"J{i+1}"
                if joint in limits:
                    if val < limits[joint]["min"] or val > limits[joint]["max"]:
                        return False, f"{joint} target {val}° outside limits [{limits[joint]['min']}, {limits[joint]['max']}]"
        
        return True, "ok"
    
    def clamp_speed(self, speed: int) -> int:
        return min(speed, self.config["max_speed"])
    
    def clamp_accel(self, accel: int) -> int:
        return min(accel, self.config["max_accel"])


class SpineTranslator:
    """Translates ICL intents to ESP32 firmware command strings."""
    
    def __init__(self, motion_port: str, io_port: str):
        self.motion = None
        self.io = None
        self.motion_port = motion_port
        self.io_port = io_port
        self.safety = SafetyEnvelope(os.path.join(CONFIG_DIR, "safety-config.json"))
        self.lock = threading.Lock()
        self.log_file = None
        self._init_logging()
        self._connect()
    
    def _init_logging(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        log_path = os.path.join(LOG_DIR, f"spine-translator-{datetime.now().strftime('%Y%m%d')}.jsonl")
        self.log_file = open(log_path, "a")
    
    def _log(self, event: str, data: dict):
        entry = {"ts": datetime.now().isoformat(), "event": event, **data}
        self.log_file.write(json.dumps(entry) + "\n")
        self.log_file.flush()
    
    def _connect(self):
        try:
            self.motion = serial.Serial(self.motion_port, BAUD_RATE, timeout=5.0)
            time.sleep(0.5)
            print(f"[OK] Motion node: {self.motion_port}")
        except serial.SerialException as e:
            print(f"[WARN] Motion node unavailable: {e}")
        
        try:
            self.io = serial.Serial(self.io_port, BAUD_RATE, timeout=5.0)
            time.sleep(0.5)
            print(f"[OK] IO node: {self.io_port}")
        except serial.SerialException as e:
            print(f"[INFO] IO node unavailable: {e}")
    
    def _send_serial(self, ser: serial.Serial, cmd: str) -> list[str]:
        """Send command string and collect responses."""
        if ser is None or not ser.is_open:
            return ["ERROR: node not connected"]
        
        with self.lock:
            ser.reset_input_buffer()
            ser.write((cmd + "\n").encode())
            
            responses = []
            start = time.time()
            while (time.time() - start) < 10.0:
                if ser.in_waiting > 0:
                    line = ser.readline().decode(errors="replace").strip()
                    if line:
                        responses.append(line)
                        if line == "END":
                            break
                time.sleep(0.005)
            
            return responses
    
    def translate_and_execute(self, intent: dict) -> dict:
        """Validate, translate, execute, and return structured result."""
        verb = intent.get("verb", "")
        t_start = time.time()
        
        # Validate safety
        ok, reason = self.safety.validate(intent)
        if not ok:
            self._log("safety_reject", {"intent": intent, "reason": reason})
            return {"success": False, "error": f"Safety: {reason}", "intent": intent}
        
        # Translate
        try:
            target, cmd = self._translate(intent)
        except ValueError as e:
            self._log("translate_error", {"intent": intent, "error": str(e)})
            return {"success": False, "error": str(e), "intent": intent}
        
        # Execute
        self._log("execute", {"target": target, "command": cmd, "intent": intent})
        
        ser = self.motion if target == "motion" else self.io
        responses = self._send_serial(ser, cmd)
        
        t_elapsed = round((time.time() - t_start) * 1000, 1)
        
        result = {
            "success": len(responses) > 0 and "Error" not in " ".join(responses),
            "intent": intent,
            "firmware_command": cmd,
            "target_node": target,
            "responses": responses,
            "latency_ms": t_elapsed,
            "timestamp": datetime.now().isoformat()
        }
        
        self._log("result", result)
        return result
    
    def _translate(self, intent: dict) -> tuple[str, str]:
        """Translate ICL intent to (target_node, firmware_command_string)."""
        verb = intent.get("verb", "")
        
        if verb == "stop":
            return ("motion", "stop")
        
        if verb == "home":
            # Home command format: Home A{order} B{order} ... 
            # For now, send simple Home
            return ("motion", "Home")
        
        if verb == "jog":
            return self._translate_jog(intent)
        
        if verb == "move_joints":
            return self._translate_move_joints(intent)
        
        if verb == "move_cartesian":
            return self._translate_move_cartesian(intent)
        
        if verb == "io_set":
            channel = intent.get("channel", 0)
            value = intent.get("value", 0)
            return ("io", f"IO_digitalWrite A{channel} B{value}")
        
        if verb == "wait":
            duration_ms = intent.get("duration_ms", 1000)
            time.sleep(duration_ms / 1000.0)
            return ("motion", "")  # No-op, just waited
        
        raise ValueError(f"Unknown ICL verb: {verb}")
    
    def _translate_jog(self, intent: dict) -> tuple[str, str]:
        """Translate jog intent to jogJ or jogL command."""
        axis = intent.get("axis", "X")
        delta = intent.get("delta_mm", 0)
        frame = intent.get("frame", "base")
        speed = self.safety.clamp_speed(intent.get("speed", 50))
        accel = self.safety.clamp_accel(intent.get("accel", 30))
        
        if frame == "base" or frame == "world":
            # Cartesian jog
            values = [0.0] * 6
            if axis in AXIS_MAP:
                values[AXIS_MAP[axis]] = delta
            
            parts = ["jogL"]
            for i in range(6):
                parts.append(f"{ALPHABET[i]}{values[i]}")
            parts.append(f"{ALPHABET[6]}{speed}")
            parts.append(f"{ALPHABET[7]}{accel}")
            
            return ("motion", " ".join(parts))
        
        elif frame == "joint":
            # Joint space jog
            joint_idx = intent.get("joint_index", 0)
            delta_deg = intent.get("delta_deg", delta)
            
            values = [0.0] * 6
            values[joint_idx] = delta_deg
            
            parts = ["jogJ"]
            for i in range(6):
                parts.append(f"{ALPHABET[i]}{values[i]}")
            parts.append(f"{ALPHABET[6]}{speed}")
            parts.append(f"{ALPHABET[7]}{accel}")
            
            return ("motion", " ".join(parts))
        
        raise ValueError(f"Unknown frame: {frame}")
    
    def _translate_move_joints(self, intent: dict) -> tuple[str, str]:
        """Translate move_joints intent to MoveJoint command."""
        targets = intent.get("joint_targets", [0] * 6)
        speed = self.safety.clamp_speed(intent.get("speed", 50))
        accel = self.safety.clamp_accel(intent.get("accel", 30))
        
        # Pad to 6 joints
        while len(targets) < 6:
            targets.append(0)
        
        parts = ["MoveJoint"]
        for i in range(6):
            parts.append(f"{ALPHABET[i]}{targets[i]}")
        parts.append(f"{ALPHABET[6]}{speed}")
        parts.append(f"{ALPHABET[7]}{accel}")
        
        return ("motion", " ".join(parts))
    
    def _translate_move_cartesian(self, intent: dict) -> tuple[str, str]:
        """Translate move_cartesian to MoveL command."""
        pose = intent.get("pose", {})
        x = pose.get("x", 0)
        y = pose.get("y", 0)
        z = pose.get("z", 0)
        yaw = pose.get("yaw", 0)
        pitch = pose.get("pitch", 0)
        roll = pose.get("roll", 0)
        speed = self.safety.clamp_speed(intent.get("speed", 50))
        accel = self.safety.clamp_accel(intent.get("accel", 30))
        
        parts = [f"MoveL A{x} B{y} C{z} D{yaw} E{pitch} F{roll} G{speed} H{accel}"]
        return ("motion", parts[0])


def serve(translator: SpineTranslator, port: int):
    """TCP server for ICL intents."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(2)
    
    print(f"\n[SPINE] ICL Translator listening on port {port}")
    print(f"  Example: echo '{{\"verb\":\"jog\",\"axis\":\"X\",\"delta_mm\":5,\"frame\":\"base\"}}' | nc pi-spine.local {port}")
    
    try:
        while True:
            conn, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(translator, conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n[SPINE] Shutting down...")
        server.close()


def handle_client(translator: SpineTranslator, conn: socket.socket, addr: tuple):
    try:
        buffer = ""
        while True:
            data = conn.recv(4096)
            if not data:
                break
            
            buffer += data.decode(errors="replace")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                
                try:
                    intent = json.loads(line)
                except json.JSONDecodeError:
                    conn.sendall(json.dumps({"error": "Invalid JSON"}).encode() + b"\n")
                    continue
                
                result = translator.translate_and_execute(intent)
                conn.sendall(json.dumps(result).encode() + b"\n")
    except (ConnectionResetError, BrokenPipeError):
        pass
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Pi Spine — ICL Translator")
    parser.add_argument("--motion-port", default="/dev/ttyUSB0")
    parser.add_argument("--io-port", default="/dev/ttyUSB1")
    parser.add_argument("--tcp-port", type=int, default=TCP_PORT)
    args = parser.parse_args()
    
    translator = SpineTranslator(args.motion_port, args.io_port)
    serve(translator, args.tcp_port)


if __name__ == "__main__":
    main()
