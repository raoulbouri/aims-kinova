# Kinova Gen3 (AIMS) — Docker workspace for macOS

Run and program the AI Maker Space **Kinova Gen3 6DoF + Robotiq 2F-85** arms from a Mac, through
Docker (ROS Noetic + `ros_kortex` + Kortex Python API 2.6.0), with a safety-gated `kinova` CLI that
a coding agent (Claude Code) can drive. See **`CLAUDE.md`** for the agent rules.

## Quick start

**0. Prerequisites:** Docker Desktop (≥ 4.27, for Compose ≥ 2.24; on Apple Silicon enable *Use Rosetta*; give it ≥ 8 GB RAM),
a USB/Thunderbolt Ethernet adapter, and your user account on the arm's web UI (see `docs/01`).

**1. Configure:**
```bash
make init                       # creates .env, then edit KINOVA_ARM / KINOVA_USERNAME / KINOVA_PASSWORD
```

**2. Build and start** (first build 20–60 min under Rosetta; it downloads from GitHub and artifactory.kinovaapps.com):
```bash
make build && make up
```

**3. Power on the arm** (docs/01): gripper unobstructed → e-stop twisted out → silver button until blue LED (**< 10 s**)
→ wait for solid green.

**4. Network:** plug in the cable, then:
```bash
./scripts/mac_network_setup.sh                          # lists adapters
./scripts/mac_network_setup.sh "USB 10/100/1000 LAN"    # 192.168.2.11/24
make preflight
```

**5. Read-only test:**
```bash
make status
```

**6. First motion** (asks you to type `yes`, e-stop in hand):
```bash
make home
```

**7. ROS / MoveIt / RViz:**
```bash
make driver          # then open http://localhost:6080 (make gui)
make moveit-home     # in another terminal
```

**8. Shutdown:** hold **A** on the Xbox pad (retract) → hold the arm near the gripper → press the e-stop.
Then `make down`.

## Docs

| File | Content |
|---|---|
| `docs/01_intro_and_setup.md` | AIMS PDF: lab rules, power on/off, Xbox, web UI, account |
| `docs/02_python_api.md` | AIMS PDF: Kortex API concepts and setup + demo scripts |
| `docs/03_ros_api.md` | AIMS PDF: ros_kortex build/launch + ROS demo |
| `docs/04_docker_macos.md` | macOS networking, noVNC GUI, Apple Silicon, building the image on a Linux server, troubleshooting |
| `docs/05_codebase_and_safety.md` | Code map, safety layers and their math, live-verified ROS topic/service map, motion self-test |

## Scripts

| File | Purpose |
|---|---|
| `scripts/preflight.sh`, `scripts/mac_network_setup.sh` | Mac network setup and checks |
| `scripts/remote_build.sh` | Build the image on a Linux server with rootless Docker, export it for `docker load` on the Mac |
| `scripts/grab_wrist_frames.py` | Read-only: save one wrist colour + depth frame (needs `vision.launch`) |
| `scripts/motion_selftest.py`, `scripts/ros_selftest.py` | End-to-end motion test (Python + ROS paths). **Moves the arm**: run only with the e-stop in reach |

`make help` lists every target.
