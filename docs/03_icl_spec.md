# Intermediate Command Language (ICL) Specification

ICL is the only language accepted by the Spine.

It must be:
- Explicit
- Unit-aware
- Frame-aware
- Deterministic
- Validatable

---

## Motion Verbs

home

jog
Required:
- axis
- delta_mm
- frame
Optional:
- speed

move_joints
Required:
- joint_targets (array)
Optional:
- velocity
- acceleration

move_cartesian
Required:
- pose (x, y, z)
Optional:
- orientation
- velocity

---

## IO Verbs

io_set
Required:
- channel
- value (0/1)

---

## Control Verbs

wait
stop

---

## Constraints

- All numeric values must include units (mm, deg).
- All deltas are bounded by configured limits.
- Speed values are clamped to maximum allowed.
- Frames must be one of: base, world, tool.
