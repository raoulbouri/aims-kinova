# Kinova Arms — API (Kortex, Python)

> Converted from the AIMS PDF **"Kinova Arms - API"**. Codebase-specific notes are marked
> **[codebase]**.

## Introduction

Kinova distributes an API (**Kortex**) for the Gen3 arms. It lets you control the arms
programmatically instead of through the web app: more control, more features and much more
automation, at the cost of needing some programming knowledge.

For more detail see the manual (*Intro and Setup* guide): **pp. 123–148** cover the robot control
types (high-level and low-level) and **pp. 228–243** cover using the API. The API exists for
Python, C++ and MATLAB (simplified). This guide covers **Python on Linux**.

- Kortex GitHub: <https://github.com/kinovarobotics/kortex>
- AIMS API tutorial: <https://github.com/CMU-AI-Maker-Space/Kinova_API_Demo_Python>
- Python docs: <https://github.com/Kinovarobotics/kortex/blob/master/api_python/doc/markdown/index.md>, <https://docs.kinovarobotics.com/index.html>
- C++ docs: <https://github.com/Kinovarobotics/kortex/blob/master/api_cpp/doc/markdown/index.md>

## Operation

The robot runs in either **high-level** or **low-level** control.

- **High-level**: easier, with more protections. **The default at boot**, and the safest and most
  straightforward mode. **The guides (and this codebase) use this mode.**
- **Low-level**: faster commands and finer control, with less protection. Advanced users should
  read the manual first.

In both modes, commands go through the **robot base**. In high-level, a command is sent to the base
as a single call through the `Kinova.Api.Base` API. Kinova's control libraries process it, at
**40 Hz**.

The robot is made of several **devices**:

- Base controller
- Actuators (each actuator is its own device)
- Interface module
- Vision module

Each device implements a set of **services**, and some services exist on several devices. A
service's methods are called through **remote procedure calls (RPC)**. In high-level mode the API
talks to the base, which passes commands to the actuators using its own control libraries.

### Connection steps

1. Open a **TCP connection** to the robot's IP (port **10000**; UDP 10001 is for low-level).
2. On that connection, start a **device router**, which delivers messages to the right device.
3. Use the router with your **credentials** to start a **session**, which proves you are an authorized user.
4. With the session open, use the **services** each device offers. For high-level control you
   mostly use the **Base** and **Vision** devices.

Messages are encoded with **Google Protocol Buffers**.

```python
from kortex_api.TCPTransport import TCPTransport
from kortex_api.RouterClient import RouterClient
from kortex_api.SessionManager import SessionManager
from kortex_api.autogen.messages import Session_pb2
from kortex_api.autogen.client_stubs.BaseClientRpc import BaseClient

transport = TCPTransport()
router = RouterClient(transport, RouterClient.basicErrorCallback)
transport.connect("192.168.2.9", 10000)                    # 1. TCP
info = Session_pb2.CreateSessionInfo()                     # 3. session
info.username, info.password = "<andrew_id>", "<password>"
info.session_inactivity_timeout = 60000                    # ms
info.connection_inactivity_timeout = 2000                  # ms
session = SessionManager(router); session.CreateSession(info)
base = BaseClient(router)                                  # 4. services
# ... use base ...
session.CloseSession(); transport.disconnect()
```

**[codebase]** `python/kinova/connection.py::KortexConnection` wraps this in a context manager.

## Setting up

The guides and the arms are set up for **v2.6.0**. Download the `.whl` from
<https://artifactory.kinovaapps.com/ui/repos/tree/General/generic-public/kortex/API/2.6.0>, then:

```bash
python3 -m pip install ./kortex_api-2.6.0.post3-py3-none-any.whl
```

(If you use a virtual environment, activate it first.)

**[codebase]** The Docker image installs the wheel automatically. Put a copy in `vendor/`
if the download fails. `protobuf` is pinned to `3.20.3`: Kortex 2.6's generated code fails with
protobuf ≥ 4 (`Descriptors cannot be created directly`).

## Scripts (AIMS demo)

AIMS provides example code covering connecting, camera access, image processing with OpenCV,
frame transformation, commanding Cartesian positions and commanding the gripper. The demo finds a
**green ball** with the arm's camera, picks it up and drops it.

> **Check the code parameters (IP, credentials) before running the files!**

| File | Purpose |
|---|---|
| `connect.py` | Opens the connection and links to the devices used. Can run on its own (change the parameters first). |
| `vision.py` | Uses the camera info and stream to find a green ball and compute its global position. Needs a robot connection. |
| `arm_mover.py` | Sends the robot and the gripper to positions. Needs a robot connection. |
| `detect_and_catch.py` | Combines everything. When the OpenCV window opens, press **`a`** ("action") once you are happy with the point the camera marks as the ball's center. |

**[codebase]** `make aims-demos` clones these into `python/external/` and `ros_ws/src/external/`.

### Key API patterns seen in the AIMS demo

- **Cartesian goal**: `Base_pb2.Action().reach_pose.target_pose.{x,y,z (m), theta_x,theta_y,theta_z (deg)}`
  then `base.ExecuteAction(action)`.
- **Wait for completion**: subscribe with `base.OnNotificationActionTopic(cb, Base_pb2.NotificationOptions())`,
  wait for `ACTION_END` / `ACTION_ABORT`, then `base.Unsubscribe(handle)`. `ExecuteAction` returns as soon
  as the command is *accepted*, not when the motion has finished.
- **Gripper**: `Base_pb2.GripperCommand()` with mode `GRIPPER_POSITION` (0 = open, 1 = closed) or
  `GRIPPER_SPEED` (in speed mode **positive opens, negative closes**); read back with
  `base.GetMeasuredGripperMovement(GripperRequest(mode=GRIPPER_POSITION))`.
- **Vision device id**: `DeviceManagerClient.ReadAllDevices()`, filter `device_type == DeviceConfig_pb2.VISION`;
  then `VisionConfigClient.GetIntrinsicParameters(sensor_id, vision_device_id)`.
