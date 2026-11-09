# Codebase map and safety model  *(codebase doc)*

## Layout

```
kinova-gen3-docker/
├── CLAUDE.md                 rules + runbook for coding agents
├── README.md                 human quick start
├── Makefile                  host-side entry points (make help)
├── docker-compose.yml        one service: `kinova`
├── .env.example              arm colour, credentials, speed caps, Docker platform
├── docker/
│   ├── Dockerfile            ROS Noetic + ros_kortex (+vision) in /opt/kinova_ws + kortex_api 2.6.0
│   ├── entrypoint.sh         sources ROS, maps KINOVA_ARM -> ROBOT_IP, starts noVNC
│   ├── with-ros.sh           wrapper for `docker compose exec`
│   ├── ros-build.sh          builds overlay /workspace/ros_ws
│   └── start-gui.sh          Xvfb + fluxbox + x11vnc + noVNC (port 6080)
├── python/                   mounted at /workspace/python (PYTHONPATH)
│   ├── kinova/               config, connection, state, motion, vision, safety, cli
│   └── examples/hello_kinova.py
├── ros_ws/src/kinova_bringup driver/vision/full/moveit_hello launches with AIMS defaults
├── scripts/                  macOS network setup + preflight (run on the Mac)
├── docs/01-03                converted AIMS PDFs; 04 Docker/macOS; 05 this file
└── vendor/                   optional: drop kortex_api-2.6.0.post3-py3-none-any.whl here
```

Inside the container: `/opt/kinova_ws` (underlay: `kortex_driver`, `kortex_move_it_config`, `kinova_vision`, ...)
and `/workspace/ros_ws` (overlay: your packages; build/devel live in Docker volumes for speed on macOS).

## Two control paths. Don't run both at once.

| | Python `kinova` package (Kortex API) | ROS `kortex_driver` + MoveIt |
|---|---|---|
| Session | Own session per command | Driver keeps one session open |
| Planning | Arm's built-in trajectory generator (straight-line Cartesian / joint interpolation) | MoveIt (OMPL), collision-aware with a scene |
| Best for | Scripts, quick moves, gripper, state, intrinsics | Planning around obstacles, perception pipelines, AIMS ROS demo |

Both send high-level commands to the same Base, so concurrent commands from both paths interfere.

## ROS interface (verified live on the green arm, 2026-11-09)

`driver.launch` (here with `start_rviz:=false start_moveit:=false`) → nodes `/my_gen3/my_gen3_driver`,
`joint_state_publisher`, `robot_state_publisher`; 283 services. `vision.launch` → `/camera/...`.

**Read (state):**

| Topic | Type | Notes |
|---|---|---|
| `/my_gen3/joint_states` | `sensor_msgs/JointState` | 40 Hz; `joint_1..joint_6` in **rad** + 6 gripper joints (`finger_joint`, knuckles); velocity, effort (Nm) |
| `/my_gen3/base_feedback` | `kortex_driver/BaseCyclic_Feedback` | 40 Hz; `base.tool_pose_{x,y,z,theta_x,theta_y,theta_z}` (m, deg), per-actuator torque/current/temp; gripper % at `interconnect.oneof_tool_feedback.gripper_feedback[0].motor[0].position` |
| `/my_gen3/action_topic` | `ActionNotification` | ACTION_START / END / ABORT |
| `/my_gen3/kortex_error`, `arm_state_topic`, `safety_topic` | | faults and state changes |
| `/tf`, `/tf_static` | | `base_link` → … → `tool_frame`, camera frames |

**Read (wrist camera, `vision.launch`, RTSP over TCP):**

| Topic | Measured |
|---|---|
| `/camera/color/image_raw` (+ `camera_info`, `image_rect_color`) | 1280×720 `rgb8`, ~31 Hz, frame `camera_color_frame`; K fx≈1298 fy≈1299 cx≈621 cy≈238 |
| `/camera/depth/image_raw` (+ `camera_info`, `image`, `image_rect`) | 480×270 `16UC1` (mm), ~21 Hz, frame `camera_depth_frame` |
| `/camera/depth/points` | point cloud |

The nodes may log `Failed to start stream` once at startup and then connect; check with `rostopic hz`.
`scripts/grab_wrist_frames.py` saves one colour + depth frame to `logs/` (read-only; `docker compose exec -T kinova with-ros.sh python3 - < scripts/grab_wrist_frames.py`).

**Command (all are motion: need human approval per CLAUDE.md):**

| Name | Kind | Use |
|---|---|---|
| `/my_gen3/in/cartesian_velocity` | topic `TwistCommand` | tool twist, while published |
| `/my_gen3/in/joint_velocity` | topic `Base_JointSpeeds` | joint speeds |
| `/my_gen3/base/play_cartesian_trajectory`, `play_joint_trajectory` | service | pose / joint goal via the Base planner |
| `/my_gen3/base/execute_action`, `read_action` | service | stored actions (`Home`, `Retract`, `Zero`, `Packaging`) |
| `/my_gen3/base/send_gripper_command` | service | gripper position 0..1 |
| `/my_gen3/gen3_joint_trajectory_controller/follow_joint_trajectory` | action | MoveIt arm trajectories |
| `/my_gen3/cartesian_trajectory_controller/follow_cartesian_trajectory` | action | Cartesian waypoints |
| `/my_gen3/robotiq_2f_85_gripper_controller/gripper_cmd` | action `GripperCommand` | MoveIt gripper |

Gotchas found while testing:
- `/my_gen3/action_topic` stays silent until you call `/my_gen3/base/activate_publishing_of_action_topic` once
  (`OnNotificationActionTopic`). Without it, nothing tells you when a `base/play_*` / `execute_action` move finished.
- `base/play_joint_trajectory` works (joint values in **degrees**, `joint_identifier` 0..5) but the driver logs that it is
  deprecated; prefer MoveIt / `follow_joint_trajectory` for new ROS code.
- Any gripper command leaves `arm_state = ARMSTATE_SERVOING_MANUALLY_CONTROLLED`. It is harmless: later moves run normally.
- If the arm link drops briefly, the driver's feedback can fail with `INVALID_USER_SESSION_ACCESS` while commands still
  go through: `joint_states` then shows **stale** values. Cross-check with `kinova status` and restart the driver.

**Motion self-test** (verified 2026-11-09, all checks passed): `scripts/motion_selftest.py A` (gripper open → Home →
±5 cm), `scripts/ros_selftest.py` (with driver + vision up: frames, J6 +10° and back over ROS), `scripts/motion_selftest.py C`
(Retract). Each step checks ACTION_END and the reached pose (≤1.5° / ≤6 mm) and stops the arm on the first anomaly.
Run as `docker compose exec -T kinova with-ros.sh python3 - A < scripts/motion_selftest.py`. Measured: Home and
Retract ≈ 2 s each, joint error ≤ 0.14°; ±5 cm Cartesian error ≤ 0.5 mm.

**Stop / recover:** `/my_gen3/in/stop` (topic) or `base/stop` (service), `in/emergency_stop`, `in/clear_faults` / `base/clear_faults`.
**Never call:** `device_config/set_i_pv4_settings`, `reboot_request`, `actuator_config/set_control_mode`, servoing/low-level services (CLAUDE.md rule 2/6).

## Safety layers (outer → inner)

1. **Human with the e-stop in reach.** The only real safety device.
2. **Lab policy** (docs/01): own account, no factory reset, no shared-config changes.
3. **Confirmation gate** (`safety.confirm`): every motion prints a summary and needs `yes` typed, or `--yes`.
   `--yes` is only for when a human has approved that exact command.
4. **Target validation** (`safety.check_cartesian` / `check_joints`), before anything is sent:
   - reach sphere ‖p‖ ≤ `R_MAX` = 0.80 m (Gen3 6DoF reach is 0.891 m; margin for the gripper and wrist singularity)
   - table plane z ≥ `Z_MIN` = 0.02 m
   - base-exclusion cylinder √(x²+y²) ≥ `RHO_MIN` = 0.15 m
   - per-command step ‖p_target − p_current‖ ≤ `MAX_STEP` = 0.30 m
   - joint limits (6DoF): J2 ±128.9°, J3 ±147.8°, J5 ±120.3°; J1, J4, J6 continuous (check against the user guide)
   - all overridable via env `KINOVA_R_MAX`, `KINOVA_Z_MIN`, `KINOVA_RHO_MIN`, `KINOVA_MAX_STEP`
5. **Speed caps**: Cartesian `reach_pose.constraint.speed` ≤ `KINOVA_MAX_LIN_SPEED` (0.10 m/s) and
   `KINOVA_MAX_ANG_SPEED` (30 °/s). The MoveIt example caps velocity/acceleration scaling at 0.5 (default 0.2).
6. **Completion monitoring**: block on `ACTION_END/ABORT`. On timeout or Ctrl-C, `Base.Stop()` is sent.
7. **Arm firmware**: joint/torque limits and protective stops.

### Why a Cartesian check isn't enough on its own
The Base moves the tool in a straight line from p₀ to p₁: p(s) = (1−s)p₀ + s·p₁, s ∈ [0,1]. The sphere and
the half-space z ≥ Z_MIN are **convex**, so if both endpoints are inside, every point on the segment is too.
The base-exclusion region (the outside of a cylinder) is **not** convex: a straight line between two valid points on
opposite sides of the base can pass through the cylinder. The MAX_STEP limit makes this much less likely, but for
big repositionings, go through `Home` or use joint moves / MoveIt.
