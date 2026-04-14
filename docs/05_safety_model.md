# Safety Envelope Model

Safety is enforced at two levels.

---

## Pi-Level (Soft Safety)

- Workspace bounds (x, y, z limits)
- Joint limits (soft bounds)
- Max delta per jog
- Max velocity cap
- Command rate limiter
- Watchdog timer (heartbeat required)
- Lock enforcement

---

## ESP-Level (Hard Safety)

- Limit switches
- Emergency stop behavior
- Local stop command
- Hardware power cutoff if implemented

---

## Design Principle

Soft safety prevents bad commands.
Hard safety prevents catastrophic failure.
