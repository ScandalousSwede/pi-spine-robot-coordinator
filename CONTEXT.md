# CASCADE-README â€” Pi Spine Dev Bundle
**For:** Cascade (Windsurf IDE) | **Date:** 2026-03-02

---

## What This Is

This bundle contains everything needed to bring up a Raspberry Pi 5 as the local coordination layer ("Spine") for Ethan's MiKoBots 6-DOF robot arm. The Pi sits between you (Cascade) and two ESP32 microcontrollers â€” one for motion (steppers + kinematics) and one for IO (relays, vacuum, inputs).

## Physical Topology

```
Your Laptop (Windsurf)
  â”‚ Ethernet (SSH to [PI_HOSTNAME])
  â”‚
  Raspberry Pi 5
  â”œâ”€â”€ /dev/ttyUSB0 â†’ Motion ESP32 (6 stepper motors, limit switches)
  â””â”€â”€ /dev/ttyUSB1 â†’ IO Box ESP32 (relays, vacuum pump)
```

## Your Access Path

1. SSH into Pi: `ssh [PI_HOSTNAME]`
2. All scripts are in `~/pi-spine/scripts/`
3. All config/logs are in `~/pi-spine/config/` and `~/pi-spine/logs/`
4. Firmware source is in `~/pi-spine/firmware/ESP32_robot_controller/`

## Critical Context

### Known Hardware State
- 6 motors respond to DIR signals (all wiring confirmed good via audio test)
- Only 3 of 6 motors locked under firmware control (GPIO pin mapping bug)
- J1 (shortest wire) and J6 (longest wire) both lock â†’ NOT a wiring issue
- Kit shipped with 1A buck converter (underpowered, may have been replaced)
- Limit switches may be wired active-high instead of active-low (or vice versa)
- Original ESP32 breakout board had pin count mismatch

### What Ethan Has Done
- Swapped drivers, rewired 24V bus, replaced buck converter
- Proved firmware was the bug using webcam + audio collection scripts
- Built all DIR-to-joint mappings
- Knows which pins are PUL but not which PUL pairs with which DIR
- Robot physically intact, no damage from the fall

### Safety Rules
- NEVER send motion commands without Ethan present and aware
- Start with minimal deltas (1-5 degrees) on any jog command
- Always home before running MoveL/MoveJ sequences
- If anything unexpected happens, send `stop\n` over serial immediately
- The robot is temporarily mounted â€” it can shift under aggressive moves

### ESP32 Firmware Command Protocol
- Baud rate: 57600
- Line ending: `\n`
- On connection, send `CONNECT\n` â†’ expect `ROBOT_CONNECTED\n`
- Flow control: ESP sends `go` when buffer has space, `wait` when nearly full
- Buffer size: 10 command slots
- Commands use alphabet-indexed parameters: `jogJ A10 B0 C0 D0 E0 F0 G50 H30`
  - A-F = joint values (J1-J6)
  - G = speed
  - H = acceleration
- After execution, ESP sends position report (`POS: X ... J1 ... J6 ...`) then `END`

### Coordination With Argus
- Desktop Coordination API runs on port 3017 (mutex lock for hardware access)
- Agent Bridge runs on port 3018 (text messaging between agents)
- During dev phase, you have direct serial access â€” no need to go through 3017
- Once Phase 5 is reached, Pi Spine will integrate with 3017 as remote lock arbiter
- Report status to Argus via bridge when completing significant milestones

## Phase-by-Phase Instructions

### Phase 1: After Ethan runs pi-provision.sh
- Verify: `python3 --version` (3.11+)
- Verify: `pip show pyserial` (installed)
- Verify: `esptool.py version` (installed)
- Verify: `arduino-cli version` (installed)

### Phase 2: After ESPs are plugged in
- Run `python3 scripts/identify-nodes.py` to determine port assignments
- Run `python3 scripts/serial-test.py CONNECT` to verify motion ESP
- Run `python3 scripts/gpio-sweep.py` with Ethan present to map pins
- Results go to `config/gpio-map.json`
- After mapping, update firmware pin assignments and flash

### Phase 3+: Software iteration
- Follow MACRO-PLAN.md phases sequentially
- Each phase has clear exit criteria â€” don't skip ahead
- Log everything â€” serial traffic, test results, timing data
- All logs go to `~/pi-spine/logs/` with ISO timestamps

