#!/usr/bin/env bash
# Host-side checks: Mac interface, subnet conflicts, reachability of the arm.
set -uo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && source .env && set +a
case "${KINOVA_ARM:-blue}" in blue) DEF=192.168.2.9;; green) DEF=192.168.2.10;; esac
IP="${ROBOT_IP:-$DEF}"
pass(){ printf "  \033[32mPASS\033[0m %s\n" "$1"; }
fail(){ printf "  \033[31mFAIL\033[0m %s\n" "$1"; }
warn(){ printf "  \033[33mWARN\033[0m %s\n" "$1"; }

echo "Arm: ${KINOVA_ARM:-blue} -> $IP"
if ifconfig 2>/dev/null | grep -q "inet 192\.168\.2\."; then
  pass "Mac has an address on 192.168.2.0/24: $(ifconfig | grep -o 'inet 192\.168\.2\.[0-9]*' | head -1)"
  n=$(ifconfig | grep -c "inet 192\.168\.2\.")
  [ "$n" -gt 1 ] && warn "More than one interface on 192.168.2.x (Wi-Fi router using the same subnet?), routing may be ambiguous"
else
  fail "No 192.168.2.x address. Run: ./scripts/mac_network_setup.sh  (docs/04_docker_macos.md)"
fi
ping -c 2 -t 3 "$IP" >/dev/null 2>&1 && pass "ping $IP" || fail "ping $IP (cable? arm powered and LED solid green?)"
nc -z -G 3 "$IP" 80    >/dev/null 2>&1 && pass "web UI  http://$IP" || fail "port 80"
nc -z -G 3 "$IP" 10000 >/dev/null 2>&1 && pass "Kortex TCP 10000" || fail "port 10000"
[ -n "${KINOVA_USERNAME:-}" ] && pass "KINOVA_USERNAME set" || fail "KINOVA_USERNAME empty in .env"
[ "${KINOVA_USERNAME:-}" = "admin" ] && fail "Do not use admin (lab policy)"
if docker info >/dev/null 2>&1; then pass "Docker running"; else fail "Docker Desktop not running"; fi
if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx kinova; then
  docker exec kinova bash -c "nc -z -w 3 $IP 10000" && pass "container -> $IP:10000" || fail "container cannot reach arm (see docs/04)"
else
  warn "container 'kinova' not running (make up)"
fi
