#!/usr/bin/env python3
"""Hardware checks left open by PR #1 (rotation via duration constraint). MOVES THE ARM.

Run by a person at the arm, e-stop in reach, tool pointing down in free space (no knob unless a step says so).
Every move asks for `yes` first; the first failure or abort stops the arm and ends the script (no retries).

  docker compose exec kinova with-ros.sh python3 /workspace/scripts/rotate_hw_checks.py A   # speed limit
  ... B   # gripper stall: is a Base.Stop() after a stall useful or harmful?
  ... C   # end-to-end: rotate_joint at the default (capped) speed, 10 then 120 deg, and back
Natively (Python 3.10 venv with kortex_api 2.6.0 + protobuf 3.20.3): python scripts/rotate_hw_checks.py A
Results are appended to logs/rotate_hw_checks.jsonl.

A  For each speed in 15, 20, 25, 30 deg/s and each chunk size in 30, 120 deg: J6 +chunk then -chunk with
   motion.reach_joints_timed (duration = chunk / speed). Records ACTION_END/ABORT and the time taken.
   Stops at the first abort. Tells us whether the limit is the average speed, the peak of the profile
   (short chunks refused first) or something else, and which ROTATE_MAX_DPS is safe.
B  Close on the knob (stall), report the arm state and grip, wait 3 s, report again; then the same with
   motion.stop() right after the stall. Then rotate J6 +30 and -30 deg with the knob held after each variant.
   Open the gripper at the end.
C  motion.rotate_joint(J6, +10), (-10), (+120), (-120) with no speed given (the cap applies).
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "python"))
from kinova import KortexConnection, load_config, motion, safety, state  # noqa: E402

J6 = 5
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "rotate_hw_checks.jsonl")


def log(rec):
    rec = dict(rec, t=time.strftime("%Y-%m-%d %H:%M:%S"))
    print(json.dumps(rec), flush=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")


def snap(k):
    s = state.snapshot(k)
    print("   now: state=%s joints=%s tool=(%.3f, %.3f, %.3f | %.1f, %.1f, %.1f) gripper=%.3f" % (
        s["arm_state"], s["joint_angles_deg"], *[s["tool_pose"][c] for c in
                                                ("x", "y", "z", "theta_x", "theta_y", "theta_z")], s["gripper"]))
    return s


def ok_or_stop(k, res, what):
    log({"step": what, **{a: b for a, b in res.items() if a != "after"}})
    if not res.get("ok"):
        motion.stop(k)
        snap(k)
        sys.exit("Stopped after %s: %s. Nothing is retried; report this in the PR." % (what, res.get("event")))


def j6_move(k, delta, duration, what):
    q = state.joint_angles(k)
    target = list(q)
    target[J6] = safety.wrap_deg(q[J6] + delta)
    safety.confirm("%s: J6 %+.0f deg in %.2f s (%.1f deg/s average), other joints held" %
                   (what, delta, duration, abs(delta) / duration), assume_yes=False)
    t0 = time.time()
    res = motion.reach_joints_timed(k, target, duration, timeout_s=2 * duration + 10)
    res["took_s"] = round(time.time() - t0, 2)
    res["got_deg"] = round(safety.wrap_deg(state.joint_angles(k)[J6] - q[J6]), 2)
    ok_or_stop(k, res, what)


def check_a(k):
    for chunk in (30.0, 120.0):
        for speed in (15.0, 20.0, 25.0, 30.0):
            for sign in (1, -1):
                j6_move(k, sign * chunk, chunk / speed, "A %g deg @ %g deg/s" % (sign * chunk, speed))
    print("A done: every combination ran. ROTATE_MAX_DPS could be raised to the highest speed that passed.")


def check_b(k):
    for with_stop in (False, True):
        safety.confirm("B (stop after stall=%s): close the gripper on the knob" % with_stop, assume_yes=False)
        res = motion.gripper(k, 1.0)
        log({"step": "B close, stop=%s" % with_stop, **res})
        if "STALLED" not in res.get("event", ""):
            motion.gripper(k, 0.0)
            sys.exit("B needs the gripper to stall on the knob; got %s" % res.get("event"))
        if with_stop:
            motion.stop(k)
        s1 = snap(k)
        time.sleep(3.0)
        s2 = snap(k)
        log({"step": "B hold 3 s, stop=%s" % with_stop, "grip_before": s1["gripper"], "grip_after": s2["gripper"],
             "state": s2["arm_state"]})
        j6_move(k, 30.0, 2.0, "B turn with knob, stop=%s" % with_stop)
        j6_move(k, -30.0, 2.0, "B turn back, stop=%s" % with_stop)
        safety.confirm("B: open the gripper", assume_yes=False)
        log({"step": "B open", **motion.gripper(k, 0.0)})
    print("B done: compare the two runs in logs/rotate_hw_checks.jsonl (grip kept? turns OK? state?).")


def check_c(k):
    for delta in (10.0, -10.0, 120.0, -120.0):
        safety.confirm("C: rotate_joint(J6, %+.0f deg), default speed (capped at %g deg/s)"
                       % (delta, motion.ROTATE_MAX_DPS), assume_yes=False)
        ok_or_stop(k, motion.rotate_joint(k, J6, delta), "C rotate %+g" % delta)
    print("C done: rotate_joint works at the default speed.")


def main():
    which = (sys.argv[1:] or [""])[0].upper()
    if which not in ("A", "B", "C"):
        sys.exit(__doc__)
    if not sys.stdin.isatty():
        sys.exit("Run this interactively (docker compose exec without -T): every move needs a typed 'yes'.")
    with KortexConnection(load_config()) as k:
        s = snap(k)
        if s["arm_state"] == "ARMSTATE_IN_FAULT":
            sys.exit("Arm is in fault; clear it by hand first.")
        {"A": check_a, "B": check_b, "C": check_c}[which](k)


if __name__ == "__main__":
    main()
