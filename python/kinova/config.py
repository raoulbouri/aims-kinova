"""Configuration from environment variables (.env is passed to the container by docker compose)."""
import os
from dataclasses import dataclass

ARM_IPS = {"blue": "192.168.2.9", "green": "192.168.2.10"}
TCP_PORT = 10000   # high-level RPC (TCP)
UDP_PORT = 10001   # low-level 1 kHz cyclic (UDP) - not used by this package


@dataclass
class RobotConfig:
    ip: str
    username: str
    password: str
    port: int = TCP_PORT
    max_lin_speed: float = 0.10   # m/s
    max_ang_speed: float = 30.0   # deg/s


def load_config(ip: str = None, username: str = None, password: str = None) -> RobotConfig:
    arm = os.environ.get("KINOVA_ARM", "blue").lower()
    ip = ip or os.environ.get("ROBOT_IP") or ARM_IPS.get(arm)
    if not ip:
        raise ValueError(f"Unknown KINOVA_ARM={arm!r} and no ROBOT_IP set")
    username = username or os.environ.get("KINOVA_USERNAME", "")
    password = password or os.environ.get("KINOVA_PASSWORD", "")
    return RobotConfig(
        ip=ip, username=username, password=password,
        max_lin_speed=float(os.environ.get("KINOVA_MAX_LIN_SPEED", 0.10)),
        max_ang_speed=float(os.environ.get("KINOVA_MAX_ANG_SPEED", 30)),
    )
