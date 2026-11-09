# Docker on macOS: networking, GUI and build notes  *(codebase doc)*

## 1. Physical + Mac network

```
 Mac (Wi-Fi: internet)          USB/Thunderbolt-Ethernet adapter
   en0  192.168.x.x  ───────    enX  192.168.2.11/24  ──── cable ────  Gen3 arm 192.168.2.9 (blue) / .10 (green)
        │
   Docker Desktop Linux VM ── container `kinova` (bridge net, NAT through the Mac)
```

1. Plug the arm's ethernet cable into the Mac (via adapter).
2. `./scripts/mac_network_setup.sh` lists services. Then
   `./scripts/mac_network_setup.sh "USB 10/100/1000 LAN"` (your adapter's name) sets `192.168.2.11 / 255.255.255.0`.
   GUI alternative: *System Settings → Network → (adapter) → Details → TCP/IP → Configure IPv4: Manually*,
   IP `192.168.2.11`, Subnet `255.255.255.0`, **Router empty**.
3. Unplug and replug the cable (AIMS guide), then `make preflight`.

**Why /24 and xx > 10**: hosts talk directly (no router) only if `IP AND mask` is equal:
`192.168.2.9 & 255.255.255.0 = 192.168.2.0 = 192.168.2.11 & 255.255.255.0`. `.9` and `.10` are the arms.
Leaving Router empty stops the Mac from making the arm link its default route, so Wi-Fi keeps your internet.

**Subnet clash**: if your Wi-Fi is also `192.168.2.0/24` (some home routers), macOS sees two routes to the same
subnet. Use a different Wi-Fi, or turn Wi-Fi off while using the arm.

## 2. Container → arm traffic

Docker Desktop for Mac runs containers in a Linux VM. **Bridge networking is enough**: outbound connections
from the container are NATed through macOS sockets, so the container reaches `192.168.2.x` through whatever
route the Mac has.

| Traffic | Protocol | Works through NAT? |
|---|---|---|
| Kortex high-level RPC | TCP 10000 (container initiates) | yes |
| Kortex low-level cyclic | UDP 10001 | request/response yes; not used here |
| Web UI | TCP 80 | yes (open it from the Mac browser directly) |
| Camera RTSP control | TCP 554 | yes |
| Camera RTP media | UDP by default: **inbound** to the container | **no**, so `vision.launch` forces `protocols=tcp` (RTP interleaved over the RTSP TCP connection) |
| ROS master / nodes | inside the container | yes (all nodes in one container) |

`network_mode: host` is not used: on Docker Desktop it is a beta opt-in feature and isn't needed.
If you later run ROS nodes on the Mac itself as well as in the container, that needs extra
`ROS_IP` / `ROS_MASTER_URI` setup. Keep all ROS nodes inside the container.

## 3. GUI (RViz, rqt, OpenCV windows)

XQuartz + OpenGL forwarding is fragile on macOS, so the container runs **Xvfb + fluxbox + x11vnc + noVNC**.
Open <http://localhost:6080/vnc.html?autoconnect=1&resize=scale> (`make gui`). Every X app in the container
(`DISPLAY=:99`) appears there. RViz uses Mesa software rendering (`LIBGL_ALWAYS_SOFTWARE=1`): it works but is slow
under emulation, so keep RViz displays minimal.

## 4. Apple Silicon (M1–M4) vs Intel

| `DOCKER_PLATFORM` | How | Status |
|---|---|---|
| `linux/amd64` (default) | Rosetta/QEMU emulation of x86 | Kinova's primary target. Build is slow (20–60 min), runtime OK |
| `linux/arm64` | Native; `kortex_driver` built with `-DCONAN_TARGET_PLATFORM=jetson` (Kinova's ARMv8 binaries) | **Experimental**: faster, but may fail to link |

Enable *Docker Desktop → Settings → General → "Use Rosetta for x86_64/amd64 emulation on Apple Silicon"*.
Give Docker Desktop **≥ 8 GB RAM** (Resources). `kortex_driver` has very large generated sources, so OOM shows up
as `c++: fatal error: Killed signal terminated program cc1plus`. In that case set `CATKIN_JOBS=1`.

The Python Kortex API is a pure-Python wheel, so it works on either architecture.

**Building on a Linux x86 server instead (what we did, 2026-11-09):** native amd64, no Rosetta, ~20 min, keeps
Mac RAM free. On xulab the repo copy is `/mnt/data/users/bbouri/kinova-gen3-docker`; `remote_build.sh` there starts a
temporary **rootless** dockerd (user not in the `docker` group; data under `/mnt/data/users/bbouri/.docker-rootless`),
builds at `nice 19`, writes `kinova-image.tar.gz` + `.sha256`, and stops the daemon. Then on the Mac:
`scp` the archive, check `shasum -a 256`, `docker load -i kinova-image.tar.gz`, `docker compose up -d --no-build`, `make ros-build`.
The container reads `.env` only at creation: after editing it, `docker compose up -d --no-build --force-recreate`.

## 5. Build-time downloads

The image build needs internet: Docker Hub (`ros:noetic-ros-base-focal`), apt, GitHub, PyPI, and
**`artifactory.kinovaapps.com`** (Kortex C++ library through conan, and the Python wheel). If Artifactory is
unreachable for the wheel, download `kortex_api-2.6.0.post3-py3-none-any.whl` manually into `vendor/`.

Conan SSL error (`certificate has expired`) during `catkin build`: add
`RUN conan config install https://github.com/conan-io/conanclientcert.git` after the conan install line in the Dockerfile.

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `kinova ping` → `kortex_10000: False` | `make preflight` on the Mac. If the Mac reaches it but the container doesn't, restart Docker Desktop (it picks up new routes on start) |
| `Descriptors cannot be created directly` | protobuf ≥ 4 got installed; `pip install protobuf==3.20.3` |
| Session error / login failed, `USER_NOT_FOUND` | Credentials in `.env`; the user must exist **on that arm's** web UI (accounts are per arm, docs/01); recreate the container after editing `.env` |
| `make ros-build` fails, `catkin init` → `profiles.yaml` not found | Fixed in `docker/ros-build.sh` (the `.catkin_tools` named volume exists empty). For an image built before the fix: `docker compose cp docker/ros-build.sh kinova:/usr/local/bin/ros-build.sh` |
| L515 / other USB RealSense | Docker Desktop on macOS has no USB passthrough; on the Mac, L515 + `pyrealsense2-macosx` 2.50 opened only under sudo and delivered no frames. Use a Linux host for it |
| `ARMSTATE_IN_FAULT` | Check the arm physically, then `kinova clear-faults`. Faults after the e-stop need the arm restarted |
| Arm moved by 7 joints / wrong URDF in RViz | You launched `kortex_driver` without `dof:=6`; use `kinova_bringup` launches |
| Camera topics silent | Use `kinova_bringup vision.launch` (TCP RTSP), check `gst-launch-1.0 rtspsrc location=rtsp://$ROBOT_IP/color protocols=tcp ! fakesink` |
| Camera topics stop mid-session (`rostopic hz` → no messages), `vision.log` shows nothing new | RTSP dropped and `kinova_vision` does not reconnect: restart `vision.launch` (kill a stuck `roslaunch` with `pkill -KILL -f roslaunch` if SIGINT hangs) |
| Driver log floods `INVALID_USER_SESSION_ACCESS` | Session lost (seen together with an RTSP stall, i.e. a brief network drop). `joint_states` is stale; check pose with `kinova status`, restart the driver |
| noVNC black screen | `docker compose exec kinova start-gui.sh`, or check `/tmp/xvfb.log` |
