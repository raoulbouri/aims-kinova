"""High-level (single-level servoing) motion commands. Every call blocks until the action
ENDs/ABORTs, and a Ctrl-C during motion sends Base.Stop()."""
import threading
import time
from contextlib import contextmanager

from . import safety, state

ACTION_TIMEOUT_S = 30.0


def ensure_high_level(k):
    from kortex_api.autogen.messages import Base_pb2
    mode = Base_pb2.ServoingModeInformation()
    mode.servoing_mode = Base_pb2.SINGLE_LEVEL_SERVOING
    k.base.SetServoingMode(mode)


def stop(k):
    """Stop the current motion (soft stop, the arm stays powered)."""
    k.base.Stop()


def clear_faults(k):
    k.base.ClearFaults()
    time.sleep(1.0)


@contextmanager
def _action_watch(k):
    """Subscribe to ActionTopic; yield (event, result). ExecuteAction only *accepts* a command,
    so completion must be observed through notifications."""
    from kortex_api.autogen.messages import Base_pb2
    done, result = threading.Event(), {}

    def cb(n):
        if n.action_event in (Base_pb2.ACTION_END, Base_pb2.ACTION_ABORT):
            result["event"] = Base_pb2.ActionEvent.Name(n.action_event)
            if n.action_event == Base_pb2.ACTION_ABORT:
                result["abort_details"] = str(n.abort_details)
            done.set()

    handle = k.base.OnNotificationActionTopic(cb, Base_pb2.NotificationOptions())
    try:
        yield done, result
    finally:
        k.base.Unsubscribe(handle)


def _run(k, send, timeout=ACTION_TIMEOUT_S) -> dict:
    ensure_high_level(k)
    with _action_watch(k) as (done, result):
        send()
        try:
            finished = done.wait(timeout)
        except KeyboardInterrupt:
            stop(k)
            return {"ok": False, "event": "STOPPED_BY_USER"}
    if not finished:
        stop(k)
        return {"ok": False, "event": "TIMEOUT"}
    return {"ok": result.get("event") == "ACTION_END", **result}


def run_stored_action(k, name: str, action_type="REACH_JOINT_ANGLES") -> dict:
    """e.g. 'Home', 'Retract', 'Zero', 'Packaging' or a pose you saved in the web app."""
    from kortex_api.autogen.messages import Base_pb2
    req = Base_pb2.RequestedActionType()
    req.action_type = getattr(Base_pb2, action_type)
    handle = next((a.handle for a in k.base.ReadAllActions(req).action_list if a.name == name), None)
    if handle is None:
        raise ValueError(f"No stored {action_type} action named {name!r}: {state.stored_actions(k, action_type)}")
    return _run(k, lambda: k.base.ExecuteActionFromReference(handle))


def move_to_pose(k, x, y, z, theta_x, theta_y, theta_z, lin_speed=None, ang_speed=None) -> dict:
    """Absolute Cartesian goal in the base frame (m, deg) with speed caps."""
    from kortex_api.autogen.messages import Base_pb2
    cur = state.tool_pose(k)
    safety.check_cartesian(x, y, z, current=(cur["x"], cur["y"], cur["z"]))

    action = Base_pb2.Action()
    action.name = "kinova_cli_reach_pose"
    action.application_data = ""
    tp = action.reach_pose.target_pose
    tp.x, tp.y, tp.z = x, y, z
    tp.theta_x, tp.theta_y, tp.theta_z = theta_x, theta_y, theta_z
    sp = action.reach_pose.constraint.speed
    sp.translation = safety.clamp_speed(lin_speed or k.cfg.max_lin_speed, k.cfg.max_lin_speed)
    sp.orientation = safety.clamp_speed(ang_speed or k.cfg.max_ang_speed, k.cfg.max_ang_speed)
    return _run(k, lambda: k.base.ExecuteAction(action))


def move_relative(k, dx=0.0, dy=0.0, dz=0.0, dthx=0.0, dthy=0.0, dthz=0.0, **kw) -> dict:
    """Translate/rotate the tool relative to its current pose (base-frame deltas)."""
    p = state.tool_pose(k)
    return move_to_pose(k, p["x"] + dx, p["y"] + dy, p["z"] + dz,
                        p["theta_x"] + dthx, p["theta_y"] + dthy, p["theta_z"] + dthz, **kw)


def move_joints(k, angles_deg) -> dict:
    from kortex_api.autogen.messages import Base_pb2
    safety.check_joints(angles_deg)
    action = Base_pb2.Action()
    action.name = "kinova_cli_reach_joints"
    action.application_data = ""
    for i, a in enumerate(angles_deg):
        ja = action.reach_joint_angles.joint_angles.joint_angles.add()
        ja.joint_identifier = i
        ja.value = a
    return _run(k, lambda: k.base.ExecuteAction(action))


def gripper(k, position: float, timeout=5.0, tol=0.01) -> dict:
    """Position mode, 0 = open, 1 = closed. Returns when the target is reached or the fingers stall
    (stall = object grasped: position stops changing before reaching the target)."""
    from kortex_api.autogen.messages import Base_pb2
    position = min(max(float(position), 0.0), 1.0)
    cmd = Base_pb2.GripperCommand()
    cmd.mode = Base_pb2.GRIPPER_POSITION
    f = cmd.gripper.finger.add()
    f.finger_identifier = 1
    f.value = position
    k.base.SendGripperCommand(cmd)

    t0, last, still_since = time.time(), None, None
    while time.time() - t0 < timeout:
        cur = state.gripper_position(k)
        if abs(cur - position) <= tol:
            return {"ok": True, "event": "REACHED", "position": cur}
        if last is not None and abs(cur - last) < 1e-3:
            still_since = still_since or time.time()
            if time.time() - still_since > 0.5 and time.time() - t0 > 0.5:
                return {"ok": True, "event": "STALLED (object?)", "position": cur}
        else:
            still_since = None
        last = cur
        time.sleep(0.05)
    return {"ok": False, "event": "TIMEOUT", "position": state.gripper_position(k)}
