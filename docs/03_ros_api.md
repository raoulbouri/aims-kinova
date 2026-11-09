# Kinova Arms — ROS API

> Converted from the AIMS PDF **"Kinova Arms - ROS API"**. Codebase-specific notes are marked
> **[codebase]**.

## Introduction

As well as the native API (Python, C++, MATLAB), Kinova publishes packages that integrate the arm
with **ROS**, so you can use ROS packages such as **MoveIt**. ROS users don't need to learn the
native API commands, but the ROS packages have **less documentation** and are **somewhat less precise**.

Tested on AIMS computers: **Ubuntu 20 + ROS Noetic**.

- ROS API: <https://github.com/Kinovarobotics/ros_kortex>
- ROS Vision API: <https://github.com/Kinovarobotics/ros_kortex_vision>
- AIMS ROS tutorial: <https://github.com/CMU-AI-Maker-Space/Kinova_API_Demo_ROS>

## Download and setup (original instructions)

```bash
mkdir -p ros_ws/src
cd ros_ws
catkin init
cd src
git clone -b noetic-devel https://github.com/Kinovarobotics/ros_kortex.git
git clone https://github.com/Kinovarobotics/ros_kortex_vision.git
cd ..
sudo python3 -m pip install conan==1.59
conan config set general.revisions_enabled=1
conan profile new default --detect > /dev/null
conan profile update settings.compiler.libcxx=libstdc++11 default
rosdep install --from-paths src --ignore-src -y
catkin build
```

You need separate packages for the **arm** (`ros_kortex`, several sub-packages) and for **vision**
(`ros_kortex_vision`). The build may show warnings but should have **no errors**. Conan must be **1.x**
(2.x does not work).

**[codebase]** All of this runs in `docker/Dockerfile`. The Kinova packages are built into
`/opt/kinova_ws` inside the image, and your own packages go in `ros_ws/src` (an overlay workspace
at `/workspace/ros_ws`).

## Running the packages

Re-source the workspace, then:

**Arm driver + MoveIt + RViz:**

```bash
roslaunch kortex_driver kortex_driver.launch ip_address:=<Robot IP> dof:=6 \
  gripper:=robotiq_2f_85 vision:=true start_rviz:=true \
  username:=<Your Username> password:=<Your Password>
```

> `dof:=6` is **required**: the driver defaults to 7 DoF for `arm:=gen3`.

When RViz opens, add a MoveIt node with **Add → Motion Planner**. Drag the arrows to move the
arm's goal, then **"Plan and Execute"** to see the motion in RViz and on the real arm.

**Vision (color + depth streams in RViz):**

```bash
roslaunch kinova_vision kinova_vision.launch device:=<Robot IP>
```

**[codebase]** Wrappers with AIMS defaults (6 DoF, Robotiq 2F-85, IP and credentials from `.env`):
`roslaunch kinova_bringup driver.launch` and `roslaunch kinova_bringup vision.launch`. The vision
wrapper forces **RTSP over TCP**, because UDP RTP streams can't get back through Docker Desktop's NAT on macOS.

Driver defaults (from `kortex_driver.launch`): `robot_name=my_gen3` (all topics and services are under
`/my_gen3/...`), `cyclic_data_publish_rate=40` Hz, `start_moveit=true`. MoveIt named arm targets:
`home`, `retract`, `vertical`. Gripper targets: `opened`, `closed`.

## Running the AIMS example code

Like the native API demo, this one tracks a green ball, plans a catch and executes it, here
using ROS nodes.

```bash
cd src && git clone https://github.com/CMU-AI-Maker-Space/Kinova_API_Demo_ROS.git
cd .. && catkin build && source devel/setup.bash
# if dependencies are missing:
rosdep install --from-paths src --ignore-src -y
pip3 install numpy opencv-python
```

The package `object_detection` has two nodes:

- **`object_tracker_node`**: finds the ball's center in 3D, publishes an image with it circled
  (`/tracking/image_with_tracking`) and stores the ball position as the ROS parameter `/ball_center`.
- **`object_catcher_node`**: moves the arm to the tracking position and then to catch the ball.

```bash
roslaunch object_detection tracking_catching.launch ip:=<ROBOT IP> username:=<Your Username> password:=<Your Password>
```

Watch the streamed image in the **rqt image viewer** (rqt opens with the launch file). When you are
happy with the tracking, call the catching service **`/my_gen3/catch_ball`** from rqt (you may need to
click refresh in rqt to see the service).

**[codebase]** `make aims-demos` clones this into `ros_ws/src/external/`, then `make ros-build`.
In the container, `opencv` comes from apt (`python3-opencv`) rather than pip, to avoid Qt plugin
clashes with ROS's `cv_bridge`.
