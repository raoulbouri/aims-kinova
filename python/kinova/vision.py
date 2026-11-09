"""Vision module helpers (Intel RealSense-based color + depth sensors in the Gen3 wrist)."""


def vision_device_id(k) -> int:
    from kortex_api.autogen.messages import DeviceConfig_pb2
    devs = k.device_manager.ReadAllDevices()
    ids = [d.device_identifier for d in devs.device_handle if d.device_type == DeviceConfig_pb2.VISION]
    if not ids:
        raise RuntimeError("No vision device found on this arm")
    return ids[0]


def intrinsics(k, sensor: str = "color") -> dict:
    """Pinhole intrinsics K = [[fx,0,cx],[0,fy,cy],[0,0,1]] for 'color' or 'depth'."""
    from kortex_api.autogen.messages import VisionConfig_pb2
    sid = VisionConfig_pb2.SensorIdentifier()
    sid.sensor = VisionConfig_pb2.SENSOR_COLOR if sensor == "color" else VisionConfig_pb2.SENSOR_DEPTH
    p = k.vision_config.GetIntrinsicParameters(sid, vision_device_id(k))
    return {
        "sensor": sensor,
        "resolution": VisionConfig_pb2.Resolution.Name(p.resolution),
        "fx": p.focal_length_x, "fy": p.focal_length_y,
        "cx": p.principal_point_x, "cy": p.principal_point_y,
        "distortion": {"k1": p.distortion_coeffs.k1, "k2": p.distortion_coeffs.k2,
                       "k3": p.distortion_coeffs.k3, "p1": p.distortion_coeffs.p1,
                       "p2": p.distortion_coeffs.p2},
    }


def rtsp_urls(ip: str) -> dict:
    return {"color": f"rtsp://{ip}/color", "depth": f"rtsp://{ip}/depth"}
