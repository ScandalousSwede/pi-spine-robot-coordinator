# pi-spine-robot-coordinator

A Raspberry Pi 5 coordination layer that sits between an AI coding agent and two ESP32 microcontrollers on a 6-DOF robot arm. Enforces a safety model requiring human presence confirmation before any motion command, defines an in-context learning specification for agent-hardware interaction, and implements multi-ESP state logging.

## System Position

```
AI Agent (laptop IDE)
        │
        │  SSH
        ▼
┌─────────────────────────────────┐
│  Raspberry Pi 5 (this repo)     │
│                                 │
│  spine-translator.py            │──── /dev/ttyUSB0 ──── Motion ESP32
│  spine-relay.py                 │                       (6 stepper motors,
│  scripts/                       │                        limit switches)
│                                 │
│  Safety model enforcement       │──── /dev/ttyUSB1 ──── IO Box ESP32
│  ICL specification              │                       (relays, vacuum pump)
│  State logging                  │
└─────────────────────────────────┘
```

The Pi is not just a router — it's the layer that enforces constraints on *what* the AI agent is permitted to do and *when*.

## Safety Model (`docs/05_safety_model.md`)

The safety model defines four rules that cannot be overridden by the AI agent:

1. **Human presence required for motion.** No motion command may execute unless the human operator has explicitly confirmed presence in the current session. The agent may not self-authorize motion.

2. **Minimal delta principle.** First commands in any session use the smallest safe delta (1–5°). The agent may not start with large-amplitude moves.

3. **Stop-on-unexpected.** If any sensor reading, motor response, or timing deviates from prediction, the agent sends `stop\n` immediately and halts the session.

4. **No autonomous homing.** Homing sequences may only run when the human has explicitly approved the home operation for that session.

These rules are encoded in the ICL specification (see below) and enforced at the Pi layer before any command reaches the ESP32 firmware.

## ICL Specification (`docs/03_icl_spec.md`)

The In-Context Learning specification defines the exact reasoning pattern the AI agent should use when operating this hardware. It covers:

- Session initialization protocol (connect → verify → confirm presence → first command)
- Command vocabulary and expected response patterns
- Error classification: recoverable (retry), operator-required (pause + ask), session-abort (stop everything)
- State tracking: what the agent must maintain in working memory across commands
- Escalation protocol: conditions under which the agent must stop and ask a human rather than continuing

The ICL spec is designed to be injected directly into the agent's system prompt, making hardware-aware behavior part of the agent's context rather than a separate enforcement layer.

## Multi-ESP Architecture (`docs/04_multi_esp_model.md`)

Two ESP32 microcontrollers handle separate subsystems:

| ESP | Port | Responsibility |
|-----|------|---------------|
| Motion | `/dev/ttyUSB0` | 6 stepper motors, limit switches, forward kinematics |
| IO Box | `/dev/ttyUSB1` | Relays (4ch), vacuum pump, digital inputs |

The Pi coordinates between them: motion commands go to the Motion ESP, end-effector commands go to the IO Box. The translator layer (`spine-translator.py`) converts high-level agent commands (`pick_up`, `place`, `jog_joint`) into the low-level firmware protocol.

## Firmware Command Protocol

```
Baud: 57600 | Line ending: \n
Connect:    CONNECT\n → ROBOT_CONNECTED\n
Jog:        jogJ A<j1> B<j2> C<j3> D<j4> E<j5> F<j6> G<speed> H<accel>\n
Flow ctrl:  ESP sends "go" (buffer available) or "wait" (buffer full)
Response:   POS: X... J1... J6...\n then END\n
```

## Scripts

| Script | Purpose |
|--------|---------|
| `pi-provision.sh` | One-shot Pi setup (Python, pyserial, esptool, arduino-cli) |
| `identify-nodes.py` | Detects which USB port is Motion vs IO ESP32 |
| `serial-test.py` | Verifies ESP32 connection and CONNECT handshake |
| `gpio-sweep.py` | Maps GPIO pin assignments with human present |
| `limit-switch-test.py` | Confirms limit switch wiring and polarity |
| `spine-translator.py` | High-level → firmware command translator |
| `spine-relay.py` | Serial relay for debugging raw firmware traffic |

## Documentation

```
docs/
├── 01_overview.md          System architecture and goals
├── 02_spine_api.md         API surface (commands the AI agent can call)
├── 03_icl_spec.md          In-context learning specification for AI agent
├── 04_multi_esp_model.md   Dual-ESP coordination model
├── 05_safety_model.md      Safety rules and enforcement
├── 06_translator_prototype.md  Command translation layer design
├── 07_skill_layer.md       Higher-level skill abstraction (pick, place, home)
├── 08_hardware_notes.md    Physical hardware state, known issues, wiring
└── pi-spine-architecture.md   Full system diagram
```

## Design Notes

The Pi-as-spine pattern was chosen to create a clear enforcement boundary. If the AI agent runs directly on the same machine as the IDE, it can potentially bypass safety checks through tool calls. A physically separate device with its own enforcement logic — where the agent communicates only via SSH and a defined command API — makes bypasses significantly harder.

The ICL specification pattern (injecting hardware rules into the agent's system prompt) was an early experiment in what the AI safety community calls "specification" — defining the constraints on agent behavior in a way the agent can reason about, rather than relying purely on external enforcement.

## Hardware

- Raspberry Pi 5 (4GB or 8GB)
- MiKoBots 6-DOF robot arm
- 2× ESP32-WROOM-32 (38-pin)
- USB-to-Serial adapters
- 6× stepper motor drivers (TB6600 or DM542)
