#!/usr/bin/env bash
# Build the user overlay workspace (/workspace/ros_ws) on top of /opt/kinova_ws.
set -e
source /opt/ros/noetic/setup.bash
source /opt/kinova_ws/devel/setup.bash
cd /workspace/ros_ws
if [ ! -f .catkin_tools/profiles/default/config.yaml ]; then
  # .catkin_tools is a named Docker volume, so it already exists (empty) and `catkin init`
  # would fail looking for profiles.yaml. Seed the minimal profile layout first.
  mkdir -p .catkin_tools/profiles/default
  [ -f .catkin_tools/profiles/profiles.yaml ] || echo "active: default" > .catkin_tools/profiles/profiles.yaml
  catkin init >/dev/null
  catkin config --extend /opt/kinova_ws/devel --cmake-args -DCMAKE_BUILD_TYPE=Release >/dev/null
fi
apt-get update -qq >/dev/null 2>&1 || true
rosdep install --from-paths src --ignore-src -y -r --rosdistro noetic || true
catkin build --no-status --summarize -j"${CATKIN_JOBS:-2}" "$@"
echo "Done. Run: source /workspace/ros_ws/devel/setup.bash"
