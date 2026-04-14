# Spine API v0 – Contract Specification

The Spine API is the single stable interface between Argus and hardware.

All hardware control flows through this interface.

---

## Lock Model

POST /lock/acquire
- Grants exclusive control to requester.
- Required before any /intent execution.

POST /lock/release
- Releases control authority.

Only one controller may hold the lock at a time.

---

## Core Endpoints

POST /intent
Body: Structured ICL payload
Behavior:
- Validate intent
- Enforce safety envelope
- Translate to node primitives
- Sequence execution
- Return structured result

POST /stop
- Immediate halt broadcast to motion node.
- Overrides lock requirement.

GET /status
Returns:
- Current lock owner
- Node connectivity state
- Last executed command
- Motion state
- Tool state
- Error flags

GET /logs/tail
Returns:
- Recent structured execution log entries

---

## Execution Semantics

Intent lifecycle:

1. Receive intent
2. Validate
3. Clamp values to safety bounds
4. Translate to primitive(s)
5. Dispatch to node(s)
6. Await ACK / DONE
7. Log outcome
