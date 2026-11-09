"""TCP -> Router -> Session -> service clients (the 4 connection steps from docs/02_python_api.md)."""
import socket

from .config import RobotConfig


def tcp_reachable(ip: str, port: int = 10000, timeout: float = 2.0) -> bool:
    """Layer-4 reachability check without opening a Kortex session."""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


class KortexConnection:
    """Context manager that always closes the session, even on exceptions / Ctrl-C.

    with KortexConnection(cfg) as k:
        k.base.GetMeasuredJointAngles()
    """

    def __init__(self, cfg: RobotConfig, session_timeout_ms: int = 60_000,
                 connection_timeout_ms: int = 2_000):
        if not cfg.username or not cfg.password:
            raise ValueError("KINOVA_USERNAME / KINOVA_PASSWORD not set (see .env)")
        if cfg.username == "admin":
            raise ValueError("Lab policy: do not use the admin account. Create your own user (docs/01).")
        self.cfg = cfg
        self.session_timeout_ms = session_timeout_ms
        self.connection_timeout_ms = connection_timeout_ms
        self._base = self._base_cyclic = self._device_manager = self._vision = None

    # -- lifecycle --------------------------------------------------------------------
    def __enter__(self):
        from kortex_api.TCPTransport import TCPTransport
        from kortex_api.RouterClient import RouterClient
        from kortex_api.SessionManager import SessionManager
        from kortex_api.autogen.messages import Session_pb2

        self.transport = TCPTransport()                                            # step 1
        self.router = RouterClient(self.transport, RouterClient.basicErrorCallback)  # step 2
        self.transport.connect(self.cfg.ip, self.cfg.port)

        info = Session_pb2.CreateSessionInfo()                                     # step 3
        info.username = self.cfg.username
        info.password = self.cfg.password
        info.session_inactivity_timeout = self.session_timeout_ms
        info.connection_inactivity_timeout = self.connection_timeout_ms
        self.session = SessionManager(self.router)
        try:
            self.session.CreateSession(info)
        except Exception:
            self.transport.disconnect()
            raise
        return self

    def __exit__(self, *exc):
        try:
            self.session.CloseSession()
        finally:
            self.transport.disconnect()
        return False

    # -- step 4: lazily created service clients ----------------------------------------
    @property
    def base(self):
        if self._base is None:
            from kortex_api.autogen.client_stubs.BaseClientRpc import BaseClient
            self._base = BaseClient(self.router)
        return self._base

    @property
    def base_cyclic(self):
        if self._base_cyclic is None:
            from kortex_api.autogen.client_stubs.BaseCyclicClientRpc import BaseCyclicClient
            self._base_cyclic = BaseCyclicClient(self.router)
        return self._base_cyclic

    @property
    def device_manager(self):
        if self._device_manager is None:
            from kortex_api.autogen.client_stubs.DeviceManagerClientRpc import DeviceManagerClient
            self._device_manager = DeviceManagerClient(self.router)
        return self._device_manager

    @property
    def vision_config(self):
        if self._vision is None:
            from kortex_api.autogen.client_stubs.VisionConfigClientRpc import VisionConfigClient
            self._vision = VisionConfigClient(self.router)
        return self._vision
