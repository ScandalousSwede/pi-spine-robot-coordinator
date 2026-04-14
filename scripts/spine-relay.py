#!/usr/bin/env python3
"""
Pi Spine — Serial Relay Server (Phase 3)
Accepts commands over TCP from Cascade/Argus, forwards to ESP32 serial,
returns responses. Logs everything.

Usage:
    python3 spine-relay.py
    python3 spine-relay.py --motion-port /dev/ttyUSB0 --io-port /dev/ttyUSB1 --tcp-port 9100

Client usage (from laptop):
    echo "CONNECT" | nc pi-spine.local 9100
    
    Or via Python:
        import socket
        s = socket.socket(); s.connect(("pi-spine.local", 9100))
        s.sendall(b'{"node": "motion", "command": "CONNECT"}\\n')
        print(s.recv(4096))
"""

import serial
import socket
import threading
import json
import time
import argparse
import os
from datetime import datetime

DEFAULT_TCP_PORT = 9100
DEFAULT_MOTION_PORT = "/dev/ttyUSB0"
DEFAULT_IO_PORT = "/dev/ttyUSB1"
BAUD_RATE = 57600
SERIAL_TIMEOUT = 5.0
LOG_DIR = os.path.expanduser("~/pi-spine/logs")


class SpineRelay:
    def __init__(self, motion_port: str, io_port: str, tcp_port: int):
        self.tcp_port = tcp_port
        self.motion_port = motion_port
        self.io_port = io_port
        self.motion_ser = None
        self.io_ser = None
        self.lock = threading.Lock()  # Only one command at a time
        self.log_file = None
        self._init_logging()
    
    def _init_logging(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        log_path = os.path.join(LOG_DIR, f"spine-relay-{datetime.now().strftime('%Y%m%d')}.jsonl")
        self.log_file = open(log_path, "a")
        self._log("system", "relay_start", {"motion": self.motion_port, "io": self.io_port, "tcp": self.tcp_port})
    
    def _log(self, category: str, event: str, data: dict = None):
        entry = {
            "ts": datetime.now().isoformat(),
            "cat": category,
            "event": event,
            "data": data or {}
        }
        self.log_file.write(json.dumps(entry) + "\n")
        self.log_file.flush()
    
    def connect_serial(self):
        """Open serial connections to ESP32 nodes."""
        try:
            self.motion_ser = serial.Serial(self.motion_port, BAUD_RATE, timeout=SERIAL_TIMEOUT)
            time.sleep(0.5)
            print(f"[OK] Motion ESP32 on {self.motion_port}")
            self._log("serial", "motion_connected", {"port": self.motion_port})
        except serial.SerialException as e:
            print(f"[WARN] Motion ESP32 not available: {e}")
            self._log("serial", "motion_failed", {"error": str(e)})
        
        try:
            self.io_ser = serial.Serial(self.io_port, BAUD_RATE, timeout=SERIAL_TIMEOUT)
            time.sleep(0.5)
            print(f"[OK] IO Box ESP32 on {self.io_port}")
            self._log("serial", "io_connected", {"port": self.io_port})
        except serial.SerialException as e:
            print(f"[INFO] IO Box ESP32 not available: {e}")
            self._log("serial", "io_unavailable", {"error": str(e)})
    
    def send_to_node(self, node: str, command: str) -> dict:
        """Send command to specified node, return structured response."""
        ser = self.motion_ser if node == "motion" else self.io_ser
        
        if ser is None or not ser.is_open:
            return {"success": False, "error": f"{node} node not connected", "responses": []}
        
        with self.lock:
            t_start = time.time()
            
            ser.reset_input_buffer()
            ser.write((command.strip() + "\n").encode())
            
            self._log("tx", "command_sent", {"node": node, "command": command.strip()})
            
            responses = []
            while (time.time() - t_start) < SERIAL_TIMEOUT:
                if ser.in_waiting > 0:
                    line = ser.readline().decode(errors="replace").strip()
                    if line:
                        responses.append(line)
                        self._log("rx", "response", {"node": node, "line": line})
                        if line == "END":
                            break
                time.sleep(0.005)
            
            t_elapsed = round((time.time() - t_start) * 1000, 1)  # ms
            
            result = {
                "success": len(responses) > 0,
                "node": node,
                "command": command.strip(),
                "responses": responses,
                "latency_ms": t_elapsed,
                "timestamp": datetime.now().isoformat()
            }
            
            self._log("result", "command_complete", {
                "node": node, 
                "command": command.strip(),
                "response_count": len(responses),
                "latency_ms": t_elapsed
            })
            
            return result
    
    def handle_client(self, conn: socket.socket, addr: tuple):
        """Handle a single TCP client connection."""
        self._log("tcp", "client_connected", {"addr": str(addr)})
        print(f"[TCP] Client connected: {addr}")
        
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
                    
                    # Try to parse as JSON
                    try:
                        request = json.loads(line)
                        node = request.get("node", "motion")
                        command = request.get("command", "")
                    except json.JSONDecodeError:
                        # Plain text — treat as motion command
                        node = "motion"
                        command = line
                    
                    if command.lower() == "stop":
                        # Emergency stop — send to all nodes
                        self._log("safety", "emergency_stop", {"source": str(addr)})
                        result_m = self.send_to_node("motion", "stop")
                        result_i = self.send_to_node("io", "stop") if self.io_ser else {}
                        result = {"motion": result_m, "io": result_i, "emergency": True}
                    elif command.lower() == "status":
                        result = {
                            "motion": {"connected": self.motion_ser is not None and self.motion_ser.is_open},
                            "io": {"connected": self.io_ser is not None and self.io_ser.is_open}
                        }
                    else:
                        result = self.send_to_node(node, command)
                    
                    response = json.dumps(result) + "\n"
                    conn.sendall(response.encode())
        
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            conn.close()
            self._log("tcp", "client_disconnected", {"addr": str(addr)})
            print(f"[TCP] Client disconnected: {addr}")
    
    def serve(self):
        """Start TCP server."""
        self.connect_serial()
        
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", self.tcp_port))
        server.listen(2)
        
        print(f"\n[RELAY] Listening on port {self.tcp_port}")
        print(f"  From laptop: echo 'CONNECT' | nc pi-spine.local {self.tcp_port}")
        print(f"  JSON mode:   echo '{{\"node\":\"motion\",\"command\":\"CONNECT\"}}' | nc pi-spine.local {self.tcp_port}")
        print(f"  Logs: {LOG_DIR}/")
        print()
        
        try:
            while True:
                conn, addr = server.accept()
                t = threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True)
                t.start()
        except KeyboardInterrupt:
            print("\n[RELAY] Shutting down...")
            self._log("system", "relay_shutdown", {})
            server.close()
            if self.motion_ser:
                self.motion_ser.close()
            if self.io_ser:
                self.io_ser.close()
            if self.log_file:
                self.log_file.close()


def main():
    parser = argparse.ArgumentParser(description="Pi Spine — Serial Relay")
    parser.add_argument("--motion-port", default=DEFAULT_MOTION_PORT)
    parser.add_argument("--io-port", default=DEFAULT_IO_PORT)
    parser.add_argument("--tcp-port", type=int, default=DEFAULT_TCP_PORT)
    args = parser.parse_args()
    
    relay = SpineRelay(args.motion_port, args.io_port, args.tcp_port)
    relay.serve()


if __name__ == "__main__":
    main()
