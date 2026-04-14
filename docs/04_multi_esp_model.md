# Multi-ESP Coordination Model

## Node Types

Motion Node
- Executes motion primitives
- Buffers commands
- Returns status

IO Node
- Controls relays
- Reports input states

Vision Node
- Publishes frames/detections
- Never controls actuators

---

## Node Discovery Protocol

On boot, Spine queries each node:

HELLO

Node responds with:
- node_id
- firmware_version
- capabilities
- health status

This allows GPIO remapping without breaking Spine logic.

---

## Coordination Strategy

Spine sequences actions across nodes.

Example Pick:

1. Motion → move to pre-grasp
2. Motion → descend
3. IO → vacuum on
4. Motion → lift
5. Motion → move to target
6. IO → vacuum off

No timing assumptions between ESPs.
Spine is timing authority.
