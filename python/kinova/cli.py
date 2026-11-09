"""`kinova` command-line tool (agent- and human-friendly).

Read-only (always safe):
  kinova ping                     TCP reachability of the arm (no login)
  kinova status [--json]          arm state, joints, tool pose, gripper
  kinova feedback [--json]        per-actuator torque/current/temperature
  kinova actions                  stored actions (Home, Retract, your saved poses)
  kinova intrinsics [--sensor color|depth]

Motion (asks for confirmation; non-interactive callers must pass --yes AFTER a human approved):
  kinova home --yes
  kinova action <name> --yes
  kinova move-rel --dz 0.05 --yes          (metres / degrees, base frame)
  kinova move-pose X Y Z TX TY TZ --yes
  kinova move-joints J1 .. J6 --yes        (degrees)
  kinova gripper 0.0|1.0 --yes             (0 open, 1 closed)
  kinova stop                              (soft stop; physical e-stop is still the real safety)
  kinova clear-faults
"""
import argparse
import json
import sys

from .config import load_config
from .connection import KortexConnection, tcp_reachable
from . import motion, safety, state, vision


def _out(obj, as_json):
    if as_json:
        print(json.dumps(obj, indent=2))
    elif isinstance(obj, dict):
        for kk, v in obj.items():
            print(f"{kk:>18}: {v}")
    else:
        print(obj)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kinova", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ip"); ap.add_argument("-u", "--username"); ap.add_argument("-p", "--password")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ping")
    sub.add_parser("status")
    sub.add_parser("feedback")
    a = sub.add_parser("actions"); a.add_argument("--type", default="REACH_JOINT_ANGLES")
    a = sub.add_parser("intrinsics"); a.add_argument("--sensor", choices=["color", "depth"], default="color")
    sub.add_parser("stop")
    sub.add_parser("clear-faults")

    def motion_parser(name, **kw):
        p = sub.add_parser(name, **kw)
        p.add_argument("--yes", action="store_true", help="skip interactive confirmation")
        return p

    motion_parser("home")
    a = motion_parser("action"); a.add_argument("name")
    a = motion_parser("move-rel")
    for f in ("dx", "dy", "dz", "dthx", "dthy", "dthz"):
        a.add_argument(f"--{f}", type=float, default=0.0)
    a.add_argument("--speed", type=float, help="m/s (capped by KINOVA_MAX_LIN_SPEED)")
    a = motion_parser("move-pose")
    for f in ("x", "y", "z", "theta_x", "theta_y", "theta_z"):
        a.add_argument(f, type=float)
    a.add_argument("--speed", type=float)
    a = motion_parser("move-joints"); a.add_argument("angles", type=float, nargs=6)
    a = motion_parser("gripper"); a.add_argument("position", type=float)

    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]       # accept --json anywhere on the line
    args = ap.parse_args(argv)
    args.json = as_json
    cfg = load_config(args.ip, args.username, args.password)

    if args.cmd == "ping":
        ok80, ok10k = tcp_reachable(cfg.ip, 80), tcp_reachable(cfg.ip, cfg.port)
        _out({"ip": cfg.ip, "web_80": ok80, "kortex_10000": ok10k}, args.json)
        return 0 if ok10k else 2

    if not tcp_reachable(cfg.ip, cfg.port):
        print(f"ERROR: {cfg.ip}:{cfg.port} unreachable. Check cable, Mac IP 192.168.2.11/24, arm LED green. "
              "See docs/04_docker_macos.md", file=sys.stderr)
        return 2

    try:
        with KortexConnection(cfg) as k:
            c = args.cmd
            if c == "status":
                _out(state.snapshot(k), args.json)
            elif c == "feedback":
                fb = state.cyclic_feedback(k)
                print(json.dumps(fb, indent=2) if args.json else
                      "\n".join(f"J{f['joint']}: q={f['position_deg']:8.2f}°  τ={f['torque_nm']:7.2f} Nm  "
                                f"I={f['current_a']:5.2f} A  T={f['temp_c']:5.1f}°C" for f in fb))
            elif c == "actions":
                _out(state.stored_actions(k, args.type), args.json)
            elif c == "intrinsics":
                _out(vision.intrinsics(k, args.sensor), args.json)
            elif c == "stop":
                motion.stop(k); print("Stop sent.")
            elif c == "clear-faults":
                motion.clear_faults(k); _out({"arm_state": state.arm_state(k)}, args.json)
            else:
                return _motion(k, args)
    except safety.SafetyError as e:
        print(f"SAFETY: {e}", file=sys.stderr)
        return 3
    return 0


def _motion(k, args):
    st = state.arm_state(k)
    if st == "ARMSTATE_IN_FAULT":
        raise safety.SafetyError("Arm is IN_FAULT. Inspect the arm, then `kinova clear-faults`.")
    c = args.cmd
    if c == "home":
        safety.confirm("run stored action 'Home'", args.yes)
        res = motion.run_stored_action(k, "Home")
    elif c == "action":
        safety.confirm(f"run stored action {args.name!r}", args.yes)
        res = motion.run_stored_action(k, args.name)
    elif c == "move-rel":
        d = dict(dx=args.dx, dy=args.dy, dz=args.dz, dthx=args.dthx, dthy=args.dthy, dthz=args.dthz)
        safety.confirm(f"relative Cartesian move {d}", args.yes)
        res = motion.move_relative(k, **d, lin_speed=args.speed)
    elif c == "move-pose":
        tgt = (args.x, args.y, args.z, args.theta_x, args.theta_y, args.theta_z)
        safety.check_cartesian(*tgt[:3])
        safety.confirm(f"Cartesian pose {tgt}", args.yes)
        res = motion.move_to_pose(k, *tgt, lin_speed=args.speed)
    elif c == "move-joints":
        safety.check_joints(args.angles)
        safety.confirm(f"joint angles {args.angles}", args.yes)
        res = motion.move_joints(k, args.angles)
    elif c == "gripper":
        safety.confirm(f"gripper -> {args.position:.2f} (0 open, 1 closed)", args.yes)
        res = motion.gripper(k, args.position)
    else:
        raise SystemExit(f"unknown command {c}")
    res["after"] = state.snapshot(k)
    _out(res, args.json)
    return 0 if res.get("ok") else 4


if __name__ == "__main__":
    sys.exit(main())
