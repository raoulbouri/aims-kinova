"""Bounded-routine approval: a human approves ONE envelope, then every command of a scripted
routine is checked against it in code instead of being approved one by one.

The envelope can only tighten the limits in `safety.py` and the speed caps in `.env`; it never
loosens them. Any failed check, abort, timeout or surprise stops the arm and ends the routine:
nothing is retried, and continuing needs a fresh human approval.
"""
import json
import math
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from . import safety


class RoutineStopped(safety.SafetyError):
    """The routine has ended (rejected command, failed motion, expiry). A human must approve a new one."""


@dataclass(frozen=True)
class Envelope:
    name: str
    box_min: List[float]                  # tool-frame position bounds in the base frame, metres
    box_max: List[float]
    max_lin_speed: float                  # m/s
    max_ang_speed: float                  # deg/s, also the cap for joint rotations
    max_tilt_deg: float = 5.0             # tool axis must stay within this of straight down
    rotate_joint: int = 6                 # the only joint the routine may spin (1-based)
    max_rotation_deg: float = 720.0       # per rotate command
    max_joint_torque_nm: Optional[float] = None   # if set, the spinning joint is stopped above this torque (backstop)
    max_step_m: float = 0.25              # per Cartesian command
    max_commands: int = 2000
    max_duration_s: float = 1800.0
    notes: str = ""

    def check_caps(self, cap_lin: float, cap_ang: float) -> None:
        errs = []
        if self.max_lin_speed > cap_lin:
            errs.append("linear speed %.3f m/s > cap %.3f" % (self.max_lin_speed, cap_lin))
        if self.max_ang_speed > cap_ang:
            errs.append("angular speed %.1f deg/s > cap %.1f" % (self.max_ang_speed, cap_ang))
        if any(lo >= hi for lo, hi in zip(self.box_min, self.box_max)) or len(self.box_min) != 3 or len(self.box_max) != 3:
            errs.append("box_min must be below box_max on all three axes")
        if self.rotate_joint - 1 not in [i for i, lim in enumerate(safety.JOINT_LIMITS_DEG) if lim is None]:
            errs.append("joint %d is not a continuous joint" % self.rotate_joint)
        if errs:
            raise safety.SafetyError("Envelope %r rejected: %s" % (self.name, "; ".join(errs)))

    def check_pose(self, x, y, z, theta_x, theta_y, theta_z=0.0, current=None) -> None:
        errs = []
        for axis, v, lo, hi in zip("xyz", (x, y, z), self.box_min, self.box_max):
            if not lo <= v <= hi:
                errs.append("%s=%.3f outside [%.3f, %.3f]" % (axis, v, lo, hi))
        tilt = tilt_from_down_deg(theta_x, theta_y)
        if tilt > self.max_tilt_deg:
            errs.append("tool tilted %.1f deg from straight down > %.1f" % (tilt, self.max_tilt_deg))
        if current is not None:
            d = math.sqrt(sum((a - b) ** 2 for a, b in zip((x, y, z), current)))
            if d > self.max_step_m:
                errs.append("step %.3f m > %.3f" % (d, self.max_step_m))
        if errs:
            raise safety.SafetyError("Outside envelope %r: %s" % (self.name, "; ".join(errs)))

    def check_rotation(self, delta_deg: float) -> None:
        if abs(delta_deg) > self.max_rotation_deg:
            raise safety.SafetyError("Outside envelope %r: rotation %.0f deg > %.0f per command"
                                     % (self.name, delta_deg, self.max_rotation_deg))

    def summary(self) -> str:
        return ("ROUTINE %r: tool stays inside x[%.3f, %.3f] y[%.3f, %.3f] z[%.3f, %.3f] m, pointing down within "
                "%.0f deg; <= %.3f m/s and <= %.0f deg/s; joint %d may spin up to %.0f deg per command%s; gripper "
                "open/close; at most %d commands or %.0f min. No further prompts until it ends. %s"
                % (self.name, self.box_min[0], self.box_max[0], self.box_min[1], self.box_max[1], self.box_min[2],
                   self.box_max[2], self.max_tilt_deg, self.max_lin_speed, self.max_ang_speed, self.rotate_joint,
                   self.max_rotation_deg,
                   " (stopped above %.2f Nm)" % self.max_joint_torque_nm if self.max_joint_torque_nm else "",
                   self.max_commands, self.max_duration_s / 60.0, self.notes))


def tilt_from_down_deg(theta_x: float, theta_y: float) -> float:
    """Angle between the tool axis and straight down, from Kortex Euler angles (deg).

    The tool z axis has base-frame z component cos(theta_x) * cos(theta_y); straight down is -1.
    """
    c = math.cos(math.radians(theta_x)) * math.cos(math.radians(theta_y))
    return math.degrees(math.acos(max(-1.0, min(1.0, -c))))


def load_envelope(path: str) -> Envelope:
    with open(path) as f:
        return Envelope(**json.load(f))


class Routine:
    """Approved once, then validates and runs commands through an arm adapter (see `arms.py`).

    `arm` provides tool_pose(), joints(), arm_state(), move_to_pose(...), rotate_joint(...),
    gripper(...), stop(). Every motion still passes through `kinova.motion` and `kinova.safety`.
    """

    def __init__(self, arm, env: Envelope, cap_lin: float, cap_ang: float, assume_yes: bool = False,
                 clock: Callable[[], float] = time.time):
        env.check_caps(cap_lin, cap_ang)
        if arm.arm_state() == "ARMSTATE_IN_FAULT":
            raise safety.SafetyError("Arm is IN_FAULT. Inspect the arm, then `kinova clear-faults`.")
        p = arm.tool_pose()
        env.check_pose(p["x"], p["y"], p["z"], p["theta_x"], p["theta_y"])   # must start inside the envelope
        safety.confirm(env.summary(), assume_yes)
        self.arm, self.env, self.clock = arm, env, clock
        self.t0 = clock()
        self.n_commands = 0
        self.stopped = None           # type: Optional[str]
        self.history = []             # type: List[Dict]

    # ---- bookkeeping -----------------------------------------------------------
    def _halt(self, reason: str) -> None:
        if self.stopped is None:
            self.stopped = reason
            try:
                self.arm.stop()
            except Exception as e:                         # the stop itself failing must not hide the reason
                self.stopped += " (and Stop failed: %s)" % e

    def _begin(self) -> None:
        if self.stopped is not None:
            raise RoutineStopped("Routine %r has ended: %s. A human must approve a new one." % (self.env.name, self.stopped))
        if self.clock() - self.t0 > self.env.max_duration_s:
            self._halt("time limit reached")
        elif self.n_commands >= self.env.max_commands:
            self._halt("command limit reached")
        if self.stopped is not None:
            raise RoutineStopped("Routine %r has ended: %s." % (self.env.name, self.stopped))
        self.n_commands += 1

    def _run(self, what: str, check: Callable[[], None], send: Callable[[], Dict]) -> Dict:
        self._begin()
        try:
            check()
            res = send()
        except RoutineStopped:
            raise
        except Exception as e:                             # rejected by a check, or the arm/connection failed
            self._halt("%s failed: %s" % (what, e))
            raise RoutineStopped("Routine %r stopped: %s" % (self.env.name, self.stopped))
        self.history.append({"t": self.clock() - self.t0, "cmd": what, "ok": bool(res.get("ok")), "event": res.get("event")})
        if not res.get("ok"):
            self._halt("%s ended with %s" % (what, res.get("event")))
        return res

    # ---- commands --------------------------------------------------------------
    def move_to_pose(self, x, y, z, theta_x, theta_y, theta_z, lin_speed=None, ang_speed=None) -> Dict:
        lin = min(lin_speed or self.env.max_lin_speed, self.env.max_lin_speed)
        ang = min(ang_speed or self.env.max_ang_speed, self.env.max_ang_speed)

        def check():
            cur = self.arm.tool_pose()
            self.env.check_pose(x, y, z, theta_x, theta_y, theta_z, current=(cur["x"], cur["y"], cur["z"]))

        return self._run("move_to_pose(%.3f, %.3f, %.3f)" % (x, y, z), check,
                         lambda: self.arm.move_to_pose(x, y, z, theta_x, theta_y, theta_z, lin, ang))

    def rotate(self, delta_deg: float, speed_dps=None) -> Dict:
        speed = min(speed_dps or self.env.max_ang_speed, self.env.max_ang_speed)

        def check():
            self.env.check_rotation(delta_deg)
            p = self.arm.tool_pose()                       # spinning the wrist is only safe with the tool vertical
            self.env.check_pose(p["x"], p["y"], p["z"], p["theta_x"], p["theta_y"])

        return self._run("rotate(J%d, %.1f deg)" % (self.env.rotate_joint, delta_deg), check,
                         lambda: self.arm.rotate_joint(self.env.rotate_joint - 1, delta_deg, speed,
                                                       max_torque_nm=self.env.max_joint_torque_nm))

    def gripper(self, position: float) -> Dict:
        return self._run("gripper(%.2f)" % position, lambda: None, lambda: self.arm.gripper(position))

    def stop(self, reason: str = "stop requested") -> None:
        self._halt(reason)
