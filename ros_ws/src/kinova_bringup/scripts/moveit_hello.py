#!/usr/bin/env python3
"""Minimal MoveIt example for the Gen3 6DoF via kortex_driver (namespace /my_gen3).

Named arm targets from gen3_robotiq_2f_85_move_it_config: home, retract, vertical.
Gripper targets: opened, closed.

  rosrun kinova_bringup moveit_hello.py __ns:=/my_gen3 --target home
  rosrun kinova_bringup moveit_hello.py __ns:=/my_gen3 --pose-dz 0.05   # lift 5 cm
"""
import argparse
import sys

import moveit_commander
import rospy


def main():
    moveit_commander.roscpp_initialize(sys.argv)
    rospy.init_node("moveit_hello")
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=None)
    ap.add_argument("--pose-dz", type=float, default=None)
    ap.add_argument("--vel-scale", type=float, default=0.2)
    args = ap.parse_args(rospy.myargv()[1:])

    ns = rospy.get_namespace()
    arm = moveit_commander.MoveGroupCommander("arm", ns=ns)
    arm.set_max_velocity_scaling_factor(min(args.vel_scale, 0.5))
    arm.set_max_acceleration_scaling_factor(min(args.vel_scale, 0.5))
    rospy.loginfo("Planning frame: %s, EE link: %s", arm.get_planning_frame(), arm.get_end_effector_link())
    rospy.loginfo("Current pose:\n%s", arm.get_current_pose().pose)

    if args.target:
        arm.set_named_target(args.target)
    elif args.pose_dz is not None:
        p = arm.get_current_pose().pose
        p.position.z += args.pose_dz
        arm.set_pose_target(p)
    else:
        rospy.loginfo("Nothing to do (pass --target or --pose-dz).")
        return

    ok = arm.go(wait=True)
    arm.stop(); arm.clear_pose_targets()
    rospy.loginfo("Motion %s", "succeeded" if ok else "FAILED")


if __name__ == "__main__":
    main()
