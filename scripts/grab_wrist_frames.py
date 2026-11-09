#!/usr/bin/env python3
"""Read-only: grab one colour + one depth frame from the wrist camera topics and save PNGs + stats."""
import sys
import numpy as np
import rospy, cv2
from cv_bridge import CvBridge
from sensor_msgs.msg import Image

out = sys.argv[1] if len(sys.argv) > 1 else "/workspace/logs/wrist"
rospy.init_node("grab_wrist_frames", anonymous=True)
br = CvBridge()
col = rospy.wait_for_message("/camera/color/image_raw", Image, timeout=20)
dep = rospy.wait_for_message("/camera/depth/image_raw", Image, timeout=20)
c = br.imgmsg_to_cv2(col, "bgr8")
d = br.imgmsg_to_cv2(dep, "passthrough").astype(np.float32) / 1000.0  # 16UC1 mm -> m
v = d[d > 0]
print(f"color {c.shape} mean={c.mean():.1f} stamp={col.header.stamp.to_sec():.3f}")
print(f"depth {d.shape} valid={v.size / d.size:.0%} min={v.min():.3f} median={np.median(v):.3f} max={v.max():.3f} m"
      f" stamp={dep.header.stamp.to_sec():.3f}")
cv2.imwrite(out + "_color.png", c)
cv2.imwrite(out + "_depth.png", cv2.applyColorMap(
    cv2.convertScaleAbs(d, alpha=255 / max(1e-3, np.percentile(v, 99))), cv2.COLORMAP_TURBO))
print("saved", out + "_color.png", out + "_depth.png")
