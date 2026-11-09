"""Read-only state queries (safe to run at any time)."""
from .safety import wrap_deg


def arm_state(k) -> str:
    from kortex_api.autogen.messages import Common_pb2
    s = k.base.GetArmState()
    return Common_pb2.ArmState.Name(s.active_state)


def servoing_mode(k) -> str:
    from kortex_api.autogen.messages import Base_pb2
    m = k.base.GetServoingMode()
    return Base_pb2.ServoingMode.Name(m.servoing_mode)


def joint_angles(k):
    """Degrees, wrapped to (-180, 180]."""
    return [wrap_deg(j.value) for j in k.base.GetMeasuredJointAngles().joint_angles]


def tool_pose(k):
    """Tool pose in the base frame: x, y, z [m], theta_x, theta_y, theta_z [deg] (Euler)."""
    p = k.base.GetMeasuredCartesianPose()
    return {"x": p.x, "y": p.y, "z": p.z, "theta_x": p.theta_x, "theta_y": p.theta_y, "theta_z": p.theta_z}


def gripper_position(k) -> float:
    """0.0 = open, 1.0 = closed."""
    from kortex_api.autogen.messages import Base_pb2
    req = Base_pb2.GripperRequest()
    req.mode = Base_pb2.GRIPPER_POSITION
    m = k.base.GetMeasuredGripperMovement(req)
    return m.finger[0].value if len(m.finger) else float("nan")


def cyclic_feedback(k):
    """Per-actuator position/velocity/torque/current/temperature from BaseCyclic (40 Hz cache)."""
    fb = k.base_cyclic.RefreshFeedback()
    return [{
        "joint": i + 1,
        "position_deg": wrap_deg(a.position),
        "velocity_dps": a.velocity,
        "torque_nm": a.torque,
        "current_a": a.current_motor,
        "temp_c": a.temperature_motor,
    } for i, a in enumerate(fb.actuators)]


def stored_actions(k, action_type: str = "REACH_JOINT_ANGLES"):
    from kortex_api.autogen.messages import Base_pb2
    req = Base_pb2.RequestedActionType()
    req.action_type = getattr(Base_pb2, action_type)
    return [a.name for a in k.base.ReadAllActions(req).action_list]


def snapshot(k) -> dict:
    return {
        "ip": k.cfg.ip,
        "arm_state": arm_state(k),
        "servoing_mode": servoing_mode(k),
        "joint_angles_deg": [round(a, 3) for a in joint_angles(k)],
        "tool_pose": {kk: round(v, 4) for kk, v in tool_pose(k).items()},
        "gripper": round(gripper_position(k), 4),
    }
