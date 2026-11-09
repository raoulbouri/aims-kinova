#!/usr/bin/env bash
# Headless X server + VNC + noVNC so RViz/rqt can be viewed at http://localhost:6080 on macOS
# (no XQuartz needed). Idempotent.
set -e
DISP=${DISPLAY:-:99}
if ! pgrep -x Xvfb >/dev/null; then
  Xvfb "$DISP" -screen 0 ${GUI_RESOLUTION:-1600x900x24} +extension GLX +render -noreset >/tmp/xvfb.log 2>&1 &
  sleep 1
fi
pgrep -x fluxbox  >/dev/null || (DISPLAY=$DISP fluxbox >/tmp/fluxbox.log 2>&1 &)
pgrep -x x11vnc   >/dev/null || x11vnc -display "$DISP" -forever -shared -nopw -quiet -rfbport 5900 >/tmp/x11vnc.log 2>&1 &
pgrep -f websockify >/dev/null || websockify --web /usr/share/novnc 6080 localhost:5900 >/tmp/novnc.log 2>&1 &
echo "[gui] noVNC: http://localhost:6080/vnc.html?autoconnect=1&resize=scale"
