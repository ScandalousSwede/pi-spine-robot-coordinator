# Pi Spine v0 — Architecture Summary
**Consolidated from ChatGPT's 8-doc spec + Argus coordination infra + Claude review**

---

## The Stack

```
Layer 3 — Argus/Cascade (Cognitive)     ← Existing, runs on desktop/laptop
  │  Long-horizon planning, skill selection, LLM workflows
  │  Ports: 3004 (Argus API), 3017 (Coordination), 3018 (Agent Bridge)
  │
  │  HTTP / TCP over LAN or Tailscale
  │
Layer 2 — Pi Spine (Coordination)        ← NEW, runs on Raspberry Pi 5
  │  Lock authority, intent validation, ICL translation
  │  Safety envelope, multi-node sequencing, logging
  │  Port: 9100 (relay) / 9200 (translator)
  │
  │  USB Serial (57600 baud)
  │
Layer 1 — ESP32 Nodes (Reflex)          ← Existing firmware, V1.22
  │  Motion execution, IO control, limit switches
  │  10-slot command buffer, go/wait flow control
  │
Layer 0 — Actuation                      ← Physical hardware
     Stepper motors, servos, vacuum, relays
```

## Four Invariants

1. No natural language below the Spine layer
2. No peer-to-peer ESP communication  
3. All hardware commands are deterministic primitives
4. Safety is layered: Pi soft safety + ESP hard safety

## Intermediate Command Language (ICL)

The only language the Spine accepts. Must be explicit, unit-aware, frame-aware, deterministic, validatable.

**Motion verbs:** home, jog, move_joints, move_cartesian
**IO verbs:** io_set
**Control verbs:** wait, stop

All numeric values include units (mm, deg). All deltas bounded by safety config. Speed clamped to max. Frames: base, world, tool, joint.

## Safety Envelope

**Pi-level (soft):** Workspace bounds, joint limits, max jog delta, velocity cap, rate limiter, heartbeat watchdog, lock enforcement.

**ESP-level (hard):** Limit switches, emergency stop, local halt on disconnect.

Soft safety prevents bad commands. Hard safety prevents catastrophic failure.

## Integration with Existing Infrastructure

The Pi Spine doesn't replace the desktop Coordination API (port 3017) — it operates underneath it.

**3017 decides WHO gets to talk to the robot** (Cascade vs Argus lock arbitration).
**Pi Spine decides HOW commands reach hardware** (validation, translation, sequencing, safety).

Migration path:
- Dev phase: Laptop → SSH → Pi → USB Serial → ESPs (direct, no 3017)
- Production: Argus/Cascade → 3017 lock → Pi Spine → ESPs

## Node Discovery

On boot, Spine sends HELLO to each serial port. Nodes respond with:
- node_id, firmware_version, capabilities, transport type, health status

This allows hot-reconfiguration without hardcoded port assignments.

## Skill Layer (Phase 6)

Skills are deterministic macro expansions of ICL primitives. They live on the Pi, not in the cloud.

Example `pick` skill:
1. move_cartesian to pre-grasp pose
2. move_cartesian descend to grasp height
3. io_set vacuum on
4. wait 500ms (vacuum settle)
5. move_cartesian lift to safe height
6. move_cartesian to target pose
7. io_set vacuum off

Skills may branch only on validated sensor state. LLM may suggest skills, but Spine executes them deterministically.

## PhD Relevance

This is substrate incompleteness theory in hardware:
- Three compute substrates (motion ESP, IO ESP, vision ESP-CAM) with different timing requirements
- Two transport substrates (USB serial, BLE) with different reliability characteristics  
- Local CNS (Pi) enforcing the boundary between symbolic reasoning and deterministic control
- The Spine IS the substrate that makes continuous, low-latency, coordinated action possible
- Without it, you get the exact failure mode the thesis predicts: dropped commands, timing conflicts, robots falling off tables
