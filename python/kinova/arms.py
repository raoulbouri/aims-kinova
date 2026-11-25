"""Arm adapters used by `Routine` and the motion server.

RealArm forwards to `kinova.motion` / `kinova.state` (so all existing guards apply).
FakeArm is a stand-in with no robot and no kortex_api, for developing and testing clients.
"""
import math
import threading
from typing import Dict, List, Optional

from . import motion, safety, state


class RealArm:
    def __init__(self, k):
        self.k = k
        self.lock = threading.Lock()                  # one Kortex call at a time (keep-alive thread vs commands)

    def tool_pose(self) -> Dict:
        with self.lock:
            return state.tool_pose(self.k)

    def joints(self) -> List[float]:
        with self.lock:
            return state.joint_angles(self.k)

    def arm_state(self) -> str:
        with self.lock:
            return state.arm_state(self.k)

    def snapshot(self) -> Dict:
        with self.lock:
            return state.snapshot(self.k)

    def move_to_pose(self, x, y, z, theta_x, theta_y, theta_z, lin_speed, ang_speed) -> Dict:
        with self.lock:
            return motion.move_to_pose(self.k, x, y, z, theta_x, theta_y, theta_z, lin_speed=lin_speed, ang_speed=ang_speed)

    def rotate_joint(self, joint_index: int, delta_deg: float, speed_dps: float, max_torque_nm=None) -> Dict:
        with self.lock:
            return motion.rotate_joint(self.k, joint_index, delta_deg, speed_dps, max_torque_nm=max_torque_nm)

    def gripper(self, position: float) -> Dict:
        with self.lock:
            return motion.gripper(self.k, position)

    def stop(self) -> None:
        motion.stop(self.k)                           # deliberately not behind the lock: Stop must always get through


class FakeArm:
    """Moves instantly and perfectly. `knob_at` makes the gripper stall there, as if holding something."""

    def __init__(self, pose: Optional[Dict] = None, joints: Optional[List[float]] = None, stall_at: Optional[float] = None):
        self.pose = dict(pose or {"x": 0.38, "y": 0.0, "z": 0.20, "theta_x": 180.0, "theta_y": 0.0, "theta_z": 90.0})
        self.q = list(joints or [0.0, 20.0, -110.0, 0.0, -50.0, 90.0])
        self.grip = 0.0
        self.stall_at = stall_at
        self.fail_next = None                         # type: Optional[str]   # event name to return once
        self.stops = 0
        self.total_rotation = 0.0

    def _result(self, **extra) -> Dict:
        if self.fail_next:
            ev, self.fail_next = self.fail_next, None
            return {"ok": False, "event": ev}
        return dict({"ok": True, "event": "ACTION_END"}, **extra)

    def tool_pose(self) -> Dict:
        return dict(self.pose)

    def joints(self) -> List[float]:
        return [safety.wrap_deg(a) for a in self.q]

    def arm_state(self) -> str:
        return "ARMSTATE_SERVOING_READY"

    def snapshot(self) -> Dict:
        return {"ip": "fake", "arm_state": self.arm_state(), "joint_angles_deg": self.joints(),
                "tool_pose": self.tool_pose(), "gripper": self.grip}

    def move_to_pose(self, x, y, z, theta_x, theta_y, theta_z, lin_speed, ang_speed) -> Dict:
        safety.check_cartesian(x, y, z, current=(self.pose["x"], self.pose["y"], self.pose["z"]))
        res = self._result()
        if res["ok"]:
            self.pose = {"x": x, "y": y, "z": z, "theta_x": theta_x, "theta_y": theta_y, "theta_z": theta_z}
        return res

    def rotate_joint(self, joint_index: int, delta_deg: float, speed_dps: float, max_torque_nm=None) -> Dict:
        self.last_max_torque_nm = max_torque_nm
        res = self._result(rotated_deg=delta_deg, chunks=max(1, int(math.ceil(abs(delta_deg) / 120.0))))
        if res["ok"]:
            self.q[joint_index] += delta_deg
            self.total_rotation += delta_deg
            self.pose["theta_z"] = safety.wrap_deg(self.pose["theta_z"] + delta_deg)
        return res

    def gripper(self, position: float) -> Dict:
        position = min(max(float(position), 0.0), 1.0)
        if self.stall_at is not None and position > self.stall_at:
            self.grip = self.stall_at
            return {"ok": True, "event": "STALLED (object?)", "position": self.grip}
        self.grip = position
        return {"ok": True, "event": "REACHED", "position": self.grip}

    def stop(self) -> None:
        self.stops += 1
