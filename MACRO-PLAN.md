# Pi Spine v0 — Macro Plan
**Created:** 2026-03-02 | **Author:** Claude (for Cascade)
**Robot:** MiKoBots 6-DOF Arm | **Spine:** Raspberry Pi 5 | **Nodes:** 2× ESP32

---

## Context

Ethan has a MiKoBots 6-DOF robot arm with known firmware GPIO mapping issues. Three of six motors lock, three don't — confirmed as firmware pin assignment bug, not wiring. All DIR signals verified via webcam + audio collection loop. J1 (shortest run) and J6 (longest run) both lock, ruling out crimping/soldering. The kit shipped with a 1A buck converter (underpowered for ESP32 + drivers). Limit switches may be wired inverted. The original ESP32 breakout board pin count didn't match.

The Pi Spine inserts a Raspberry Pi 5 between Cascade/Argus and the ESP32 nodes as a local coordination layer. Phase 0 priority is: get the robot moving safely so it doesn't fall again.

## Hardware Topology (Dev Phase)

```
Laptop (Cascade / Windsurf)
  │
  Ethernet (SSH)
  │
  Raspberry Pi 5
  ├── USB Serial (/dev/ttyUSB0) → Motion ESP32 (6-DOF steppers + kinematics)
  └── USB Serial (/dev/ttyUSB1) → IO Box ESP32 (relays, vacuum, inputs)
```

Production topology (later) may move Vision ESP32-CAM to BLE and connect Argus (desktop) over LAN/Tailscale.

---

## Phase 1 — Raspberry Pi Reboot & Provision
**Goal:** Pi 5 boots headless, SSH-accessible, with all dev tools installed.
**Duration:** 1-2 hours (mostly waiting for flashing + installs)
**Prerequisite:** Pick a Pi (OctoPrint or cat fountain Pi), microSD card, ethernet cable

### Tasks
- Flash Raspberry Pi OS Lite (64-bit, Bookworm) to microSD
- Enable SSH + set hostname to `pi-spine` in Imager settings
- Boot Pi, connect via ethernet to laptop
- Run `pi-provision.sh` (included in bundle) which installs:
  - Python 3.11+, pip, venv
  - pyserial, esptool
  - arduino-cli (for firmware compilation + flashing)
  - screen / minicom (serial debug)
  - git, vim, htop
- Verify SSH works: `ssh ethan@pi-spine.local`
- Verify USB serial detection: `ls /dev/ttyUSB*` (should show nothing yet — no ESPs plugged in)

### Exit Criteria
- [ ] Pi boots headless and is SSH-accessible from laptop
- [ ] All dev tools installed and verified
- [ ] Pi hostname resolves as `pi-spine.local`

---

## Phase 1.5 — Physical Setup
**Goal:** Robot mounted safely on workbench, Pi physically connected to both ESPs.
**Duration:** 1-3 hours depending on mounting approach
**Prerequisite:** Phase 1 complete, workbench ready, command hooks

### Tasks
- Mount robot to workbench using command hooks (temporary, sufficient for dev)
- Ensure robot base is stable — hand test: push gently from each direction, no wobble
- Position Pi near IO Box (ideal mounting point per MiKoBots assembly guide)
- Cable runs:
  - USB-A → micro-USB/USB-C: Pi to Motion ESP32
  - USB-A → micro-USB/USB-C: Pi to IO Box ESP32
  - Ethernet: Pi to laptop
  - Power: Pi to nearest outlet (USB-C PD)
- Power on Pi, SSH in
- Verify both ESPs detected: `ls /dev/ttyUSB*` → should show two devices
- Run `identify-nodes.py` (included) to determine which ttyUSB is motion vs IO
- Label cables physically (painter's tape + sharpie is fine)

### Exit Criteria
- [ ] Robot stable on workbench
- [ ] Pi connected to both ESPs via USB
- [ ] Both serial devices detected by Pi
- [ ] Motion vs IO ESP identified and labeled
- [ ] `serial-test.py CONNECT` returns `ROBOT_CONNECTED` from motion ESP
- [ ] `serial-test.py CONNECT --port /dev/ttyUSB1` returns `IO_CONNECTED` from IO ESP (if IO firmware is flashed)

---

## Phase 2 — GPIO Mapping & Firmware
**Goal:** Complete verified GPIO pin map for new ESP32, flash working firmware to both nodes, achieve single-axis movement.
**Duration:** 2-4 sessions (this is the hard part)
**Prerequisite:** Phase 1.5 complete, new ESP32 board available

### Tasks

#### 2a — GPIO Discovery
- Run `gpio-sweep.py` (included): systematically toggles each GPIO pin, Ethan observes which driver responds
- Build verified map: `{GPIO_pin: joint, signal_type: "DIR"|"PUL"|"LIMIT"}`
- For each joint, confirm DIR and PUL pair
- For limit switches: run `limit-switch-test.py` to read each input pin and determine active-high vs active-low (resolves the inversion question)
- Output: `gpio-map.json` — the single source of truth

#### 2b — Firmware Configuration
- Edit ESP32 firmware pin assignments to match verified `gpio-map.json`
- Flash motion firmware via Pi: `esptool.py --port /dev/ttyUSB0 write_flash ...`
- Flash IO firmware via Pi: `esptool.py --port /dev/ttyUSB1 write_flash ...`
- Compile using arduino-cli on Pi (or cross-compile on laptop and push binary)

#### 2c — Single Axis Validation
- For each joint J1-J6:
  - Send `jogJ` command for that joint only (small delta, low speed)
  - Confirm motor moves in correct direction
  - Confirm motor stops at correct position
  - Check limit switch triggers correctly
  - Log results to `validation-log.json`
- Fix any reversed directions (DirJoint parameter in firmware)
- Fix any incorrect step-per-degree ratios

#### 2d — Homing Sequence
- Run `Home` command
- Verify each joint homes in correct order
- Verify limit switch polarity (robot moves toward switch, stops on trigger)
- Adjust HomingOrder and PosLimitSwitch in firmware as needed

### Exit Criteria
- [ ] All 6 joints verified: DIR, PUL, limit switch mapped and tested
- [ ] `gpio-map.json` complete and validated
- [ ] Firmware flashed to both ESPs with correct pin config
- [ ] Each joint moves independently on command
- [ ] Homing sequence completes successfully
- [ ] All validation results logged

---

## Phase 3 — Serial Relay & Logging (Pi Spine Phase 0-1)
**Goal:** Pi becomes the command relay with full observability.
**Duration:** 1-2 sessions
**Prerequisite:** Phase 2 complete, robot moves on all 6 axes

### Tasks
- Deploy `spine-relay.py` (included): accepts commands over TCP from laptop, forwards to correct ESP serial port, returns response
- Add structured logging: every command, response, and timing measurement written to `spine-log.jsonl`
- Cascade can now send commands from Windsurf without direct serial access
- Test full command set through relay: Home, jogJ, jogL, MoveJ, MoveL, IO commands
- Measure round-trip latency: command sent → response received
- Verify no commands dropped under rapid sequencing

### Exit Criteria
- [ ] Cascade can command robot via TCP through Pi relay
- [ ] All commands logged with timestamps
- [ ] Latency measured and documented
- [ ] No dropped commands in burst test (10 rapid jog commands)

---

## Phase 4 — Spine Translator & ICL (Pi Spine Phase 2)
**Goal:** Pi accepts structured ICL intents instead of raw firmware command strings.
**Duration:** 2-3 sessions
**Prerequisite:** Phase 3 complete and stable

### Tasks
- Deploy `spine-translator.py` based on Pi Spine doc 06 prototype
- Implement ICL verb handlers: home, jog, move_joints, move_cartesian, io_set, wait, stop
- Implement unit validation (all values must include mm/deg)
- Implement frame awareness (base/world/tool)
- Test: send ICL intent `{"verb": "jog", "axis": "X", "delta_mm": 10, "frame": "base"}` → Pi translates to `jogL A10 B0 C0 D0 E0 F0 G50 H30` → ESP executes → Pi returns structured result
- Build ICL test suite covering all verbs

### Exit Criteria
- [ ] All ICL verbs implemented and tested
- [ ] Unit validation catches bad inputs (missing units, out-of-range)
- [ ] Structured JSON responses from every command
- [ ] Test suite passes

---

## Phase 5 — Safety Envelope & Lock Model (Pi Spine Phase 3)
**Goal:** Pi enforces safety bounds and exclusive access control.
**Duration:** 2-3 sessions
**Prerequisite:** Phase 4 complete

### Tasks
- Implement workspace bounds (configurable x/y/z limits in `safety-config.json`)
- Implement joint limits (soft bounds from firmware config)
- Implement velocity caps and command rate limiting
- Implement watchdog: if no heartbeat from controller within N seconds, halt
- Implement lock model: acquire/release, only one controller at a time
- Implement emergency stop: `/stop` bypasses lock, broadcasts halt to motion ESP
- Connect to desktop Coordination API (port 3017) as remote lock arbiter
- Test: send command that exceeds workspace → Pi rejects before it reaches ESP
- Test: two controllers try to send simultaneously → lock prevents collision

### Exit Criteria
- [ ] All safety bounds enforced and tested
- [ ] Lock model prevents concurrent access
- [ ] Emergency stop works from any state
- [ ] Watchdog halts on lost connection
- [ ] Integration with 3017 Coordination API confirmed

---

## Phase 6 — Skill Layer & Argus Integration
**Goal:** Deterministic macro skills, full Argus connectivity, production topology.
**Duration:** 3-5 sessions
**Prerequisite:** Phase 5 complete

### Tasks
- Implement skill expansion: `prep_workspace`, `pick`, `place`, `park`
- Each skill is a deterministic sequence of ICL primitives
- Connect Argus (desktop) → Pi Spine over LAN/Tailscale
- Add Vision ESP32-CAM node (BLE) for on-arm camera
- Implement node discovery protocol (HELLO → capabilities response)
- Run first autonomous pick-and-place sequence commanded by Argus
- Document full architecture for PhD portfolio

### Exit Criteria
- [ ] At least 3 skills implemented and tested
- [ ] Argus can command robot remotely through Pi Spine
- [ ] Vision node integrated (even if just frame capture)
- [ ] Full architecture documented with timing data
- [ ] Portfolio-ready demo recorded

---

## Timeline Estimate

| Phase | Effort | Depends On |
|-------|--------|------------|
| 1 — Pi Provision | 1-2 hours | microSD + Pi available |
| 1.5 — Physical Setup | 1-3 hours | Phase 1 + command hooks |
| 2 — GPIO & Firmware | 2-4 sessions | Phase 1.5 + new ESP32 |
| 3 — Serial Relay | 1-2 sessions | Phase 2 (robot moves) |
| 4 — ICL Translator | 2-3 sessions | Phase 3 (relay stable) |
| 5 — Safety & Lock | 2-3 sessions | Phase 4 (ICL works) |
| 6 — Skills & Argus | 3-5 sessions | Phase 5 (safety enforced) |

**Phases 1-2 are the critical path.** Once you have movement on all 6 axes, everything else is software iteration on a working platform.

**Phase 2 is where the real debugging happens.** GPIO mapping is the task that blocked you last time. The difference now: Cascade has serial access through the Pi and can run systematic pin sweeps instead of manual visual tracing.

---

## Files in This Bundle

```
pi-spine-bundle/
├── MACRO-PLAN.md              ← You are here
├── CASCADE-README.md          ← Instructions for Cascade
├── scripts/
│   ├── pi-provision.sh        ← Run on Pi after first boot
│   ├── serial-test.py         ← Basic serial connectivity test
│   ├── identify-nodes.py      ← Determine which ttyUSB is which ESP
│   ├── gpio-sweep.py          ← Systematic GPIO pin toggle for mapping
│   ├── limit-switch-test.py   ← Read limit switch states + polarity
│   ├── spine-relay.py         ← TCP-to-serial relay (Phase 3)
│   └── spine-translator.py    ← ICL intent translator (Phase 4)
├── firmware/
│   └── ESP32_robot_controller/  ← MiKoBots V1.22 firmware source
├── config/
│   ├── gpio-map-template.json ← Template for GPIO mapping results
│   └── safety-config.json     ← Default safety envelope bounds
└── docs/
    ├── esp32-command-reference.md  ← All firmware commands documented
    └── pi-spine-architecture.md    ← Consolidated architecture spec
```
