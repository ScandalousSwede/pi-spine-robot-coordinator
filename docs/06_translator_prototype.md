# Spine Translator – Reference Prototype

This is a conceptual reference implementation.

import serial

class SpineTranslator:

    def __init__(self, motion_port, io_port):
        self.motion = serial.Serial(motion_port, 57600)
        self.io = serial.Serial(io_port, 57600)

    def send_motion(self, cmd):
        self.motion.write((cmd + "\n").encode())

    def send_io(self, cmd):
        self.io.write((cmd + "\n").encode())

    def translate_intent(self, intent):

        if intent["type"] == "motion":
            if intent["verb"] == "home":
                return ("motion", "Home")

            if intent["verb"] == "jog":
                axis = intent["axis"].upper()
                delta = intent["delta_mm"]
                return ("motion", f"jogL {axis} {delta}")

        if intent["type"] == "io":
            if intent["verb"] == "set":
                channel = intent["channel"]
                value = intent["value"]
                return ("io", f"IO_digitalWrite {channel} {value}")

        raise ValueError("Unsupported intent")

    def execute_intent(self, intent):
        target, cmd = self.translate_intent(intent)

        if target == "motion":
            self.send_motion(cmd)

        if target == "io":
            self.send_io(cmd)
