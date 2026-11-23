"""Exercise the public translator's software bounds. No device is opened."""
import runpy
from pathlib import Path

source = Path(__file__).resolve().parents[1] / "scripts" / "spine-translator.py"
envelope = runpy.run_path(str(source))["SafetyEnvelope"]()
for target in (0, 999):
    intent = {"verb": "move_joints", "joint_targets": [target, 0, 0, 0, 0, 0]}
    ok, reason = envelope.validate(intent)
    print(f"J1 target {target:3} degrees: {'pass' if ok else 'reject'} ({reason})")
