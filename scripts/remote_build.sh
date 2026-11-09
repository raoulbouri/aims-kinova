#!/usr/bin/env bash
# Builds kinova-gen3-noetic:latest on xulab with a temporary rootless dockerd (no docker group needed),
# saves it to kinova-image.tar.gz, then stops the daemon. CPU only, nice 19, 2 catkin jobs.
set -uo pipefail
R=/mnt/data/users/bbouri/kinova-gen3-docker
export XDG_RUNTIME_DIR=/mnt/data/users/bbouri/.dr
mkdir -p "$XDG_RUNTIME_DIR" && chmod 700 "$XDG_RUNTIME_DIR"
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/docker.sock
cd "$R"
echo "[$(date)] starting rootless dockerd"
nice -n 19 dockerd-rootless.sh --data-root /mnt/data/users/bbouri/.docker-rootless > logs/dockerd.log 2>&1 &
DPID=$!
for i in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 2; done
docker info --format 'dockerd up: {{.ServerVersion}} driver={{.Driver}} rootless' || { echo "dockerd failed"; kill $DPID; exit 1; }
echo "[$(date)] build start"
nice -n 19 docker build --progress=plain --platform linux/amd64 \
  --build-arg CATKIN_JOBS=2 --build-arg WITH_GAZEBO=false \
  -f docker/Dockerfile -t kinova-gen3-noetic:latest . ; RC=$?
echo "[$(date)] build exit=$RC"
if [ $RC -eq 0 ]; then
  docker images kinova-gen3-noetic
  nice -n 19 bash -c 'docker save kinova-gen3-noetic:latest | gzip -1 > kinova-image.tar.gz.part' && mv kinova-image.tar.gz.part kinova-image.tar.gz
  ls -lh kinova-image.tar.gz && sha256sum kinova-image.tar.gz > kinova-image.tar.gz.sha256
fi
echo "[$(date)] stopping dockerd"; kill $DPID; wait $DPID 2>/dev/null
echo "[$(date)] DONE rc=$RC"
