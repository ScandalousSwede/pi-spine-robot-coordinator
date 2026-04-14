# Pi Spine v0 – System Architecture Overview

Generated: 2026-03-02_05-08-10

## Core Design Thesis

One embodied robot = one local CNS (Pi / Jetson class computer).

Microcontrollers (ESP32 nodes) are deterministic reflex controllers.
They execute motion and IO with strict timing guarantees.
They do NOT coordinate each other.

All coordination, translation, safety validation, and logging converges at the Pi.

---

## Architectural Layers

Layer 3 – Argus (Cognitive Layer)
- Long-horizon planning
- Skill selection
- Scheduling / cron logic
- Experimental LLM workflows
- Never touches hardware directly

Layer 2 – Pi Spine (Coordination Layer)
- Lock authority
- Intent validation
- Skill expansion
- Multi-node sequencing
- Safety envelope enforcement
- Logging and replay
- State aggregation

Layer 1 – ESP32 Nodes (Reflex Layer)
- Motion execution (step/dir, buffers)
- IO relay control
- Limit switch handling
- Local emergency stop

Layer 0 – Actuation
- Stepper drivers
- Relays
- Vacuum pump
- Physical hardware

---

## Invariants

1. No natural language below the Spine layer.
2. No peer-to-peer ESP communication.
3. All hardware commands are deterministic primitives.
4. Safety is layered (Pi soft safety, ESP hard safety).
