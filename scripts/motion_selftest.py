#!/usr/bin/env python3
"""Motion self-test, Python/Kortex path. Runs ONE phase, checks every result, stops on the first anomaly.

  phase A: gripper 0 (open) -> Home -> move-rel dz +0.05 -> dz -0.05      (from rest, ends at Home)
  phase C: Retract                                                        (from Home, ends at rest)

Run inside the container only after a human approved this exact sequence (CLAUDE.md rule 1):
  docker compose exec -T kinova with-ros.sh python3 - A < scripts/motion_selftest.py
Exit 0 = all checks passed; 3 = anomaly (Base.Stop sent, nothing else attempted).
"""
import sys, time
from kinova import KortexConnection, load_config, state, motion, safety

JOINT_TOL_DEG = 1.5
POS_TOL_M = 0.006
TARGETS = {"Home": [0.0, 15.0, -130.0, 0.0, 55.0, 90.0], "Retract": [0.0, -20.0, -146.0, 0.0, -50.0, 90.0]}
BAD_STATES = ("ARMSTATE_IN_FAULT", "ARMSTATE_MAINTENANCE", "ARMSTATE_UNDEFINED")


class Anomaly(Exception):
    pass


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def snap(k):
    s = state.snapshot(k)
    log(f"   state={s['arm_state']} joints={s['joint_angles_deg']} "
        f"tool=({s['tool_pose']['x']:.3f},{s['tool_pose']['y']:.3f},{s['tool_pose']['z']:.3f}) gripper={s['gripper']:.3f}")
    if s["arm_state"] in BAD_STATES:
        raise Anomaly(f"arm state {s['arm_state']}")
    return s


def joint_err(a, b):
    return max(abs(safety.wrap_deg(x - y)) for x, y in zip(a, b))


def expect_ok(res, what):
    log(f"   result: {res}")
    if not res.get("ok"):
        raise Anomaly(f"{what} did not end with ACTION_END/REACHED: {res}")


def phase_a(k):
    s0 = snap(k)
    log("A1 gripper -> 0 (open)")
    expect_ok(motion.gripper(k, 0.0), "gripper 0")
    s = snap(k)
    if s["gripper"] > 0.03:
        raise Anomaly(f"gripper at {s['gripper']:.3f}, expected ~0")
    if joint_err(s["joint_angles_deg"], s0["joint_angles_deg"]) > 0.5:
        raise Anomaly("joints moved during a gripper-only command")

    log("A2 stored action Home")
    expect_ok(motion.run_stored_action(k, "Home"), "Home")
    s = snap(k)
    e = joint_err(s["joint_angles_deg"], TARGETS["Home"])
    log(f"   max joint error vs Home target: {e:.2f} deg")
    if e > JOINT_TOL_DEG:
        raise Anomaly(f"not at Home (max joint error {e:.2f} deg)")

    for dz in (+0.05, -0.05):
        p0 = s["tool_pose"]
        log(f"A3 move-rel dz={dz:+.2f} m at 0.05 m/s")
        expect_ok(motion.move_relative(k, dz=dz, lin_speed=0.05), f"move-rel dz={dz}")
        s = snap(k)
        p = s["tool_pose"]
        err = max(abs(p["x"] - p0["x"]), abs(p["y"] - p0["y"]), abs(p["z"] - (p0["z"] + dz)))
        log(f"   max position error: {err * 1000:.1f} mm")
        if err > POS_TOL_M:
            raise Anomaly(f"tool off target by {err * 1000:.1f} mm")
    e = joint_err(s["joint_angles_deg"], TARGETS["Home"])
    log(f"   back at Home, max joint error {e:.2f} deg")


def phase_c(k):
    s = snap(k)
    if joint_err(s["joint_angles_deg"], TARGETS["Home"]) > 3.0:
        raise Anomaly("phase C expects to start at Home")
    log("C1 stored action Retract")
    expect_ok(motion.run_stored_action(k, "Retract"), "Retract")
    s = snap(k)
    e = joint_err(s["joint_angles_deg"], TARGETS["Retract"])
    log(f"   max joint error vs Retract target: {e:.2f} deg")
    if e > JOINT_TOL_DEG:
        raise Anomaly(f"not at Retract (max joint error {e:.2f} deg)")


def main():
    phase = sys.argv[1].upper()
    with KortexConnection(load_config()) as k:
        try:
            {"A": phase_a, "C": phase_c}[phase](k)
        except Exception as ex:
            log(f"!! ANOMALY in phase {phase}: {ex}")
            motion.stop(k)
            log("!! Base.Stop sent. Not continuing.")
            try:
                snap(k)
            except Exception:
                pass
            return 3
    log(f"phase {phase}: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
