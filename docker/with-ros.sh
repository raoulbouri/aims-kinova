#!/usr/bin/env bash
# Run any command with ROS + both workspaces sourced and ROBOT_IP resolved.
# Needed for `docker compose exec` (which bypasses the entrypoint and non-interactive .bashrc).
source /usr/local/bin/entrypoint.sh --source-only
exec "$@"
