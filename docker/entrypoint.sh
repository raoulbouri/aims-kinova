#!/usr/bin/env bash
# Sources ROS + workspaces. With --source-only it only sources (used from .bashrc).
source /opt/ros/noetic/setup.bash
[ -f /opt/kinova_ws/devel/setup.bash ] && source /opt/kinova_ws/devel/setup.bash
[ -f /workspace/ros_ws/devel/setup.bash ] && source /workspace/ros_ws/devel/setup.bash

# Map the arm colour to an IP if ROBOT_IP is not set explicitly.
if [ -z "${ROBOT_IP:-}" ]; then
  case "${KINOVA_ARM:-blue}" in
    blue)  export ROBOT_IP=192.168.2.9 ;;
    green) export ROBOT_IP=192.168.2.10 ;;
  esac
fi

[ "${1:-}" = "--source-only" ] && return 0 2>/dev/null

if [ "${START_GUI:-1}" = "1" ]; then
  /usr/local/bin/start-gui.sh
fi
exec "$@"
