# Safety envelope and operating requirements

The public translator implements software input checks. The intended attended system also requires controls in the operator workflow, firmware and hardware.

| Control | Evidence or responsibility |
| --- | --- |
| Jog delta, speed, acceleration, joint bounds | [SafetyEnvelope.validate](../scripts/spine-translator.py) implements checks for the corresponding verbs and supplied fields. The [offline example](../examples/check_bounds.py) exercises a valid and an out-of-range joint target. |
| Cartesian workspace bounds | Defaults are declared in the translator. The validator does not enforce Cartesian endpoint bounds from these settings. |
| Human presence, minimal first motion and specific homing approval | Operating requirements. This snapshot contains no presence token or homing-approval check. |
| Command-rate limit, heartbeat watchdog and ownership lock | Design requirements. Their enforcement is not demonstrated by the public translator. |
| Limit switches, emergency stop and power cutoff | Verify on the specific installed firmware and physical system before claiming these protections. |

A successful software bounds check shows that a particular input passed the implemented rules. It does not establish physical reachability or unattended safety.
