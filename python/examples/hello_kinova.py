"""Minimal library usage example: read state, then (after confirmation) a 5 cm lift and back.

    python3 python/examples/hello_kinova.py          # inside the container
"""
import json

from kinova import KortexConnection, load_config
from kinova import motion, safety, state

cfg = load_config()
with KortexConnection(cfg) as k:
    print(json.dumps(state.snapshot(k), indent=2))
    safety.confirm("lift tool 5 cm, then return", assume_yes=False)
    print(motion.move_relative(k, dz=+0.05))
    print(motion.move_relative(k, dz=-0.05))
