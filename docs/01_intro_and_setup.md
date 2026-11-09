# Kinova Arms — Intro and Setup

> Converted from the AIMS PDF **"Kinova Arms - Intro and Setup"**. Figures in the PDF
> (resting pose, Xbox layouts, login page, new-user form) are described in text here.

## Introduction

Kinova makes robotic arms that are mostly used in research. They are very precise,
but not very strong or powerful. The AI Maker Space (AIMS) has **two Kinova Gen3 6DoF
arms**, each fitted with a **Robotiq 2F-85 gripper** end-effector. One arm has a
**blue band** and the other a **green band**.

These guides are a short version of how to get the arms running. For more depth:

- Kinova Gen3 6DoF manual: `EN-UG-014-Gen3-Ultra-lightweight-user-guide-r9.1.pdf`
- YouTube tutorial playlist: <https://www.youtube.com/watch?v=zQewb08M4sA&list=PLz1XwEYRuku5rZjJWBr6SDi93jgWZ4FHL>
- Kinova website: <https://www.kinovarobotics.com/product/gen3-robots>

### Tech summary of the AIMS arms

| Item | Value |
|---|---|
| Firmware version | 2.5.2 (newest available) |
| Optimized computer | Mead |
| ROS version tested | Noetic with Ubuntu 20 |

## Key warnings (lab policy: violations revoke access)

- **DO** read the canvas guides before working with the arms, **even if you are an experienced user**.
- **DO NOT** factory reset the arms without explicit approval from staff **each time**. Everyone else loses their work.
- **DO NOT** change shared configurations, such as the arm's **IP address**, without explicit approval from staff each time.
- **DO NOT** work directly in the **admin** account.
- **DO NOT** clutter the table the arms sit on.
- **DO NOT** unplug or move the arms.
- **DO** save custom configurations (trajectories, poses) with a name that **contains your andrew id**, so staff can track who is doing what.

## Starting, using and stopping the arms

### Starting

1. The arm should be resting in its folded (retracted) position, as shown in the PDF figure.
2. **The gripper must not be blocked**: the arm opens and closes the gripper when it starts up.
   If the gripper is blocked, gently move the arm until it rests in a stable position with
   the gripper free to open and close.
3. Check that the **power supply** is connected and switched on.
4. Find the **red e-stop button** and **keep it within reach at all times**. Unlock the
   robot by twisting the e-stop in the direction of the arrow on it. The button should pop out.
5. Press the **silver button on the back of the arm** until a **blue LED** lights up, then release.
   **DO NOT press the button for more than 10 seconds: that factory resets the arm.**
6. The lights show **blue and yellow** while it starts up. When the gripper has **closed and opened**
   and the light is **solid green**, the arm is ready.

### Using: Xbox controller

Use the Xbox controller attached to the arm to check that it works. There are three default layouts
(shown as figures in the PDF):

- **Twist linear controls**: Cartesian translation of the end-effector
- **Twist angular controls**: Cartesian rotation of the end-effector
- **Joint controls**: move one joint at a time

Spend some time driving the robot in every layout to see how each behaves. (Exercise from the guide:
work out what the **"toggle admittance"** button does.)

- Press **RB** to **lock** the robot whenever it is not in use, to avoid accidental movements.
- Press **LB** to **unlock** it before using it again.

### Using: web interface

The web interface is for two things:

1. **Creating your own account**, which registers you as an active user of the arm so staff can see it.
2. The simplest way to control the arm programmatically, which is a good start if you have little coding experience.

> **Note:** users are separate, but **arm configurations are shared** whoever set them.
> **DO NOT change settings like the IP or the firmware type.** Only change things fundamental to your
> project (for example camera resolution or custom poses). When in doubt, ask staff.
>
> **Note:** for the same reason, **check that all essential configurations are correct before running
> your code**. Another user may have changed them.

The web interface's address is the arm's IP (it is also marked on the arm):

| Robot | IP |
|---|---|
| Blue | `192.168.2.9` |
| Green | `192.168.2.10` |

Connect the robot's **ethernet cable** to your laptop. To reach the robot you must be on the same
network, so set your wired connection to:

| IPv4 | Subnet mask |
|---|---|
| `192.168.2.xx` | `255.255.255.0` |

Here **xx is a number greater than 10** (11 is common). Where to change IP settings depends on
your OS. After changing them, **unplug and replug the cable** to reset the connection.

Open a browser at `http://<robot-ip>`. You will see the login page.

Use the admin account **only once**, to create your own account:

| Login | Password |
|---|---|
| `admin` | `admin` |

Create your account: click the **three bars** next to the Kinova logo (top left) → **Users** → the
**plus sign** (bottom right). Fill in the form:

| Field | Value |
|---|---|
| Username | **Your andrew id.** Profiles that do not follow this pattern will be deleted |
| Password | Your choice |
| First/last name | Your name as registered with the university (or close enough to identify you) |
| User type | **research** |
| Notes | A short description of why you are using the arms. For an official research project or course, include the advisor/instructor name |

Add the profile, **log out of admin** and log in to your new profile.

Test: click the **"pose"** icon at the bottom of the screen and try to move the robot. You can also
test actions, admittances, etc.

### Stopping

1. **Press and hold "A"** on the Xbox controller until the arm stops moving. This takes the arm
   to the **retracted** position.
2. Once it is retracted, **hold the arm with one hand near the gripper** and **hit the red e-stop**
   with the other. The arm goes **limp**. Let go once it is resting stably against itself.

The arm is now safely shut down. Arrange the cables neatly after disconnecting them.

## Ways to use the arms

| | Web App | API (Kortex) | ROS |
|---|---|---|---|
| **Pros** | Easiest to use; least experience required; graphical interface | Integrates with Python/C++/MATLAB; native commands | Integrates with ROS and its tools (MoveIt, CvBridge) |
| **Cons** | Very little customization; only simple problems; limited programming | Needs some setup and coding skill | Needs coding and ROS proficiency; documentation is thin, so some reverse engineering of the Kinova ROS packages is needed |
