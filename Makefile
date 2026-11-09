# Run these on your Mac (host). Everything robot-related runs inside the `kinova` container.
SHELL := /bin/bash
DC    := docker compose
EXEC  := $(DC) exec -T kinova /usr/local/bin/with-ros.sh
ARGS  ?=

.PHONY: help init build up down shell gui preflight test ping status feedback actions intrinsics \
        home stop ros-build driver driver-nogui vision full moveit-home aims-demos logs clean

help:            ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

init:            ## create .env from template
	@test -f .env || (cp .env.example .env && echo "Created .env, fill in KINOVA_USERNAME / KINOVA_PASSWORD")

build: init      ## build the Docker image (first time: 20-60 min under Rosetta)
	$(DC) build

up: init         ## start the container in the background
	$(DC) up -d
	@echo "GUI (RViz/rqt): http://localhost:6080/vnc.html?autoconnect=1&resize=scale"

down:            ## stop the container
	$(DC) down

shell:           ## interactive bash inside the container
	$(DC) exec kinova bash

gui:             ## open noVNC in your browser (macOS)
	open "http://localhost:6080/vnc.html?autoconnect=1&resize=scale"

preflight:       ## host-side network checks (Mac -> arm)
	./scripts/preflight.sh

# ---------- Python Kortex API (read-only) ----------
test:            ## offline unit tests (no arm needed)
	$(EXEC) python3 -m unittest discover -s /workspace/python/tests -v
ping:            ## TCP reachability from inside the container
	$(EXEC) kinova ping
status:          ## arm state, joints, tool pose, gripper
	$(EXEC) kinova status $(ARGS)
feedback:        ## per-actuator torque/current/temp
	$(EXEC) kinova feedback $(ARGS)
actions:         ## list stored actions
	$(EXEC) kinova actions
intrinsics:      ## camera intrinsics
	$(EXEC) kinova intrinsics $(ARGS)

# ---------- motion (interactive confirmation; -it keeps a TTY) ----------
home:            ## move to stored Home (asks for confirmation)
	$(DC) exec kinova /usr/local/bin/with-ros.sh kinova home
stop:            ## soft-stop current motion
	$(EXEC) kinova stop

# ---------- ROS ----------
ros-build:       ## build overlay workspace ros_ws/src
	$(EXEC) ros-build.sh
driver:          ## kortex_driver + MoveIt + RViz (view in noVNC)
	$(DC) exec kinova /usr/local/bin/with-ros.sh roslaunch kinova_bringup driver.launch
driver-nogui:    ## kortex_driver + MoveIt, no RViz
	$(DC) exec kinova /usr/local/bin/with-ros.sh roslaunch kinova_bringup driver.launch start_rviz:=false
vision:          ## color/depth streams
	$(DC) exec kinova /usr/local/bin/with-ros.sh roslaunch kinova_bringup vision.launch
full:            ## driver + vision + RViz + image viewer
	$(DC) exec kinova /usr/local/bin/with-ros.sh roslaunch kinova_bringup full.launch
moveit-home:     ## MoveIt to named target 'home' (driver must be running)
	$(DC) exec kinova /usr/local/bin/with-ros.sh roslaunch kinova_bringup moveit_hello.launch target:=home

aims-demos:      ## clone AIMS Python + ROS demos (then: make ros-build)
	@mkdir -p python/external ros_ws/src/external
	@test -d python/external/Kinova_API_Demo_Python || git clone https://github.com/CMU-AI-Maker-Space/Kinova_API_Demo_Python.git python/external/Kinova_API_Demo_Python
	@test -d ros_ws/src/external/Kinova_API_Demo_ROS || git clone https://github.com/CMU-AI-Maker-Space/Kinova_API_Demo_ROS.git ros_ws/src/external/Kinova_API_Demo_ROS

logs:            ## container logs
	$(DC) logs -f kinova

clean:           ## remove container + build volumes (keeps image)
	$(DC) down -v
