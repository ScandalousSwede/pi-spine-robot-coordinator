# Pi Spine

Pi Spine translates structured requests for a MiKo robot arm into serial messages for its motion and I/O controllers. The public Raspberry Pi prototype includes a Python translator, diagnostic tools and the design specifications for an attended workshop system.

## Run a check without hardware

Use Python 3.9 or later in a virtual environment. The example loads the translator’s actual `SafetyEnvelope` class and checks two inputs against its default joint limits. It opens no serial port, starts no listener and transmits no commands.

```console
python3 -m pip install pyserial==3.5
python3 examples/check_bounds.py
```

The zero-degree target passes. The deliberately out-of-range 999-degree target is rejected locally. This demonstrates an input check before translation. Physical position, calibration and interlock behavior require separate bench evidence.

## What the public prototype implements

| Layer | Behavior in this snapshot |
| --- | --- |
| [Translator](scripts/spine-translator.py) | Validates configured jog delta, maximum speed/acceleration and limits for the supplied joint targets. Translates structured verbs, exchanges serial messages and logs requests and responses. |
| [Session and safety design](docs/05_safety_model.md) | Calls for an attending operator, minimal initial moves, explicit homing authorization and stopping on unexpected behavior. Human presence and homing authorization must be provided by the surrounding operating system or operator workflow. |
| Firmware and physical hardware | Limit switches, emergency stop and power cutoff depend on the actual controller, wiring and bench configuration. The software-only example establishes none of those. |

The public translator has no per-session human-presence or homing-permission check. Treat this snapshot as an engineering prototype for attended development.

## Source and design notes

- [Translator prototype](docs/06_translator_prototype.md) and [architecture](docs/pi-spine-architecture.md)
- [In-context learning specification](docs/03_icl_spec.md) and [multi-controller model](docs/04_multi_esp_model.md)
- [Hardware notes](docs/08_hardware_notes.md) and [diagnostic scripts](scripts)

The serial diagnostics and relay are separate tools. The bounds example exercises the translator class only.
