#!/usr/bin/env python3
"""Motion self-test, ROS path (phase B). Needs driver.launch + vision.launch running and the Python path idle.

  B1 read /my_gen3/joint_states, check it matches the expected start (Home)
  B2 grab one wrist colour + depth frame (read-only)
  B3 /my_gen3/base/play_joint_trajectory: J6 +10 deg, wait ACTION_END, verify via joint_states
  B4 same service: J6 back to start, verify

On any anomaly: /my_gen3/base/stop, exit 3, nothing else attempted.
  docker compose exec -T kinova with-ros.sh python3 - < scripts/ros_selftest.py
"""
import math, sys, time, threading
import numpy as np
import rospy, cv2
from cv_bridge import CvBridge
from sensor_msgs.msg import Image, JointState
from kortex_driver.msg import ActionNotification, ActionEvent, JointAngle
from kortex_driver.srv import PlayJointTrajectory, PlayJointTrajectoryRequest, Stop, OnNotificationActionTopic, \
    OnNotificationActionTopicRequest

NS = "/my_gen3"
HOME = [0.0, 15.0, -130.0, 0.0, 55.0, 90.0]
TOL = 1.5
OUT = "/workspace/logs/selftest_wrist"


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def joints_deg():
    js = rospy.wait_for_message(f"{NS}/joint_states", JointState, timeout=5)
    return [round(math.degrees(js.position[js.name.index(f"joint_{i}")]), 2) for i in range(1, 7)]


class Anomaly(Exception):
    pass


ev = {"done": threading.Event(), "event": None}


def on_action(n):
    if n.action_event in (ActionEvent.ACTION_END, ActionEvent.ACTION_ABORT):
        ev["event"] = "ACTION_END" if n.action_event == ActionEvent.ACTION_END else f"ACTION_ABORT {n.abort_details}"
        ev["done"].set()


def play(target, timeout=30):
    req = PlayJointTrajectoryRequest()
    for i, v in enumerate(target):
        ja = JointAngle(); ja.joint_identifier = i; ja.value = v % 360.0
        req.input.joint_angles.joint_angles.append(ja)
    ev["done"].clear(); ev["event"] = None
    rospy.ServiceProxy(f"{NS}/base/play_joint_trajectory", PlayJointTrajectory)(req)
    if not ev["done"].wait(timeout):
        raise Anomaly("no ACTION_END within timeout")
    if ev["event"] != "ACTION_END":
        raise Anomaly(ev["event"])
    time.sleep(0.5)
    got = joints_deg()
    err = max(abs(wrap(a - b)) for a, b in zip(got, target))
    log(f"   reached {got}, max joint error {err:.2f} deg")
    if err > TOL:
        raise Anomaly(f"joint error {err:.2f} deg > {TOL}")


def main():
    rospy.init_node("ros_selftest", anonymous=True, disable_signals=True)
    rospy.Subscriber(f"{NS}/action_topic", ActionNotification, on_action)
    rospy.wait_for_service(f"{NS}/base/play_joint_trajectory", timeout=20)
    # The driver only publishes ActionNotifications on action_topic after this call (ros_kortex examples do the same).
    rospy.ServiceProxy(f"{NS}/base/activate_publishing_of_action_topic", OnNotificationActionTopic)(
        OnNotificationActionTopicRequest())
    start = [float(a) for a in sys.argv[1:7]] if len(sys.argv) >= 7 else None  # resume: explicit target to return to
    try:
        log("B1 joint_states")
        j0 = joints_deg()
        err = max(abs(wrap(a - b)) for a, b in zip(j0, HOME))
        log(f"   {j0} (max error vs Home {err:.2f} deg)")
        if err > 3.0 and not (start and abs(wrap(j0[5] - start[5] - 10.0)) < TOL
                              and max(abs(wrap(a - b)) for a, b in zip(j0[:5], HOME[:5])) < 3.0):
            raise Anomaly("not at Home (or Home with J6 +10 deg when resuming) before ROS test")

        log("B2 wrist camera frames")
        br = CvBridge()
        col = rospy.wait_for_message("/camera/color/image_raw", Image, timeout=20)
        dep = rospy.wait_for_message("/camera/depth/image_raw", Image, timeout=20)
        c = br.imgmsg_to_cv2(col, "bgr8")
        d = br.imgmsg_to_cv2(dep, "passthrough").astype(np.float32) / 1000.0
        v = d[d > 0]
        log(f"   color {c.shape} mean={c.mean():.1f}; depth {d.shape} valid={v.size / d.size:.0%} median={np.median(v):.3f} m")
        cv2.imwrite(OUT + "_color.png", c)
        cv2.imwrite(OUT + "_depth.png", cv2.applyColorMap(
            cv2.convertScaleAbs(d, alpha=255 / max(1e-3, np.percentile(v, 99))), cv2.COLORMAP_TURBO))

        if start is None:
            t1 = list(j0); t1[5] = j0[5] + 10.0
            log(f"B3 play_joint_trajectory J6 {j0[5]:.1f} -> {t1[5]:.1f} deg")
            play(t1)
            start = j0
        log(f"B4 play_joint_trajectory J6 back to {start[5]:.1f} deg")
        play(start)
    except Exception as ex:
        log(f"!! ANOMALY: {ex}")
        try:
            rospy.ServiceProxy(f"{NS}/base/stop", Stop)()
            log("!! base/stop sent. Not continuing.")
        except Exception as e2:
            log(f"!! base/stop failed: {e2}")
        return 3
    log("phase B: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
