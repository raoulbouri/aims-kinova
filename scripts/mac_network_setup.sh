#!/usr/bin/env bash
# Give the Mac's wired (USB/Thunderbolt Ethernet) interface a static IP on the arm's subnet.
#   ./scripts/mac_network_setup.sh                       # list services
#   ./scripts/mac_network_setup.sh "USB 10/100/1000 LAN"  # set 192.168.2.11/24
#   ./scripts/mac_network_setup.sh "USB 10/100/1000 LAN" dhcp   # revert
set -euo pipefail
if [[ "$(uname)" != "Darwin" ]]; then echo "macOS only"; exit 1; fi
if [[ $# -lt 1 ]]; then
  echo "Network services on this Mac (pick your Ethernet adapter):"
  networksetup -listallnetworkservices | tail -n +2
  exit 0
fi
SERVICE="$1"; MODE="${2:-static}"; IP="${MAC_IP:-192.168.2.11}"
if [[ "$MODE" == "dhcp" ]]; then
  sudo networksetup -setdhcp "$SERVICE"; echo "Reverted '$SERVICE' to DHCP"; exit 0
fi
# No router argument: the arm subnet must not become the default route (keeps Wi-Fi internet working).
sudo networksetup -setmanual "$SERVICE" "$IP" 255.255.255.0
echo "Set '$SERVICE' -> $IP/24. Unplug and replug the arm cable, then: make preflight"
