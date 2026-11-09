# syntax=docker/dockerfile:1
# Kinova Gen3 (6DoF + Robotiq 2F-85) dev image: ROS Noetic + ros_kortex + kortex_api (Python)
# Built for Docker Desktop on macOS. Default platform is linux/amd64 (Rosetta on Apple Silicon),
# because Kinova's prebuilt C++ Kortex library (pulled by conan) targets x86 first.
FROM ros:noetic-ros-base-focal

ARG TARGETARCH
ARG CATKIN_JOBS=2
ARG WITH_GAZEBO=false
ARG KORTEX_WHEEL_URL=https://artifactory.kinovaapps.com/artifactory/generic-public/kortex/API/2.6.0/kortex_api-2.6.0.post3-py3-none-any.whl

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1

# ---- system packages: build tools, MoveIt/RViz/rqt, GStreamer (vision), headless GUI (noVNC) ----
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential git curl wget ca-certificates nano less \
      python3-pip python3-catkin-tools python3-rosdep python3-opencv python3-numpy python3-scipy \
      ros-noetic-rviz ros-noetic-moveit ros-noetic-moveit-commander \
      ros-noetic-rqt ros-noetic-rqt-common-plugins ros-noetic-rqt-image-view ros-noetic-rqt-service-caller \
      ros-noetic-cv-bridge ros-noetic-tf2-ros ros-noetic-image-pipeline ros-noetic-rgbd-launch \
      gstreamer1.0-tools gstreamer1.0-libav gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
      gstreamer1.0-plugins-bad libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
      xvfb x11vnc fluxbox novnc websockify xterm libgl1-mesa-dri mesa-utils \
      iputils-ping netcat-openbsd iproute2 \
    && rm -rf /var/lib/apt/lists/*

# ---- conan 1.x (ros_kortex fetches the C++ Kortex API through it; 2.x is NOT supported) ----
RUN python3 -m pip install --no-cache-dir "conan==1.59" \
 && conan config set general.revisions_enabled=1 \
 && conan profile new default --detect > /dev/null \
 && conan profile update settings.compiler.libcxx=libstdc++11 default

# ---- Kinova ROS packages in an underlay workspace ----
WORKDIR /opt/kinova_ws
RUN mkdir -p src && cd src \
 && git clone --depth 1 -b noetic-devel https://github.com/Kinovarobotics/ros_kortex.git \
 && git clone --depth 1 https://github.com/Kinovarobotics/ros_kortex_vision.git \
 && if [ "$WITH_GAZEBO" != "true" ]; then touch ros_kortex/kortex_gazebo/CATKIN_IGNORE; fi

RUN apt-get update && rosdep update --rosdistro noetic \
 && rosdep install --from-paths src --ignore-src -y -r --rosdistro noetic \
 && rm -rf /var/lib/apt/lists/*

# Apple-Silicon native (linux/arm64) builds use Kinova's ARMv8 "jetson" binaries (experimental).
RUN . /opt/ros/noetic/setup.sh \
 && catkin init \
 && catkin config --extend /opt/ros/noetic \
 && EXTRA=""; if [ "$TARGETARCH" = "arm64" ]; then EXTRA="-DCONAN_TARGET_PLATFORM=jetson"; fi \
 && catkin config --cmake-args -DCMAKE_BUILD_TYPE=Release $EXTRA \
 && catkin build --no-status --summarize -j"${CATKIN_JOBS}" -p1 \
 && rm -rf build logs

# ---- Python Kortex API 2.6.0 (pure-python wheel; vendor/ copy wins if present) ----
COPY vendor/ /tmp/vendor/
RUN set -e; WHL=$(ls /tmp/vendor/kortex_api-*.whl 2>/dev/null | head -n1 || true); \
    if [ -z "$WHL" ]; then \
      WHL=/tmp/kortex_api-2.6.0.post3-py3-none-any.whl; \
      curl -fSL --retry 3 -o "$WHL" "$KORTEX_WHEEL_URL"; \
    fi; \
    python3 -m pip install --no-cache-dir "$WHL" "protobuf==3.20.3" pyyaml \
 && python3 -c "import kortex_api, google.protobuf as p; print('kortex_api OK, protobuf', p.__version__)" \
 && rm -rf /tmp/vendor /tmp/*.whl

# ---- runtime ----
COPY docker/entrypoint.sh docker/start-gui.sh docker/ros-build.sh docker/with-ros.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/*.sh \
 && printf '#!/bin/sh\nexec python3 -m kinova.cli "$@"\n' > /usr/local/bin/kinova && chmod +x /usr/local/bin/kinova \
 && echo 'source /usr/local/bin/entrypoint.sh --source-only' >> /root/.bashrc

ENV PYTHONPATH=/workspace/python \
    DISPLAY=:99 \
    LIBGL_ALWAYS_SOFTWARE=1 \
    QT_X11_NO_MITSHM=1

WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sleep", "infinity"]
