"""Offline tests (no robot, no kortex_api needed):  python3 -m unittest discover -s python/tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from kinova import safety  # noqa: E402


class TestSafety(unittest.TestCase):
    def test_home_like_pose_ok(self):
        safety.check_cartesian(0.45, 0.0, 0.43)

    def test_rejections(self):
        for p in [(0.9, 0, 0.3), (0.4, 0, 0.0), (0.05, 0.05, 0.5)]:
            with self.assertRaises(safety.SafetyError):
                safety.check_cartesian(*p)

    def test_max_step(self):
        with self.assertRaises(safety.SafetyError):
            safety.check_cartesian(0.45, 0.3, 0.3, current=(0.45, -0.2, 0.3))

    def test_wrap(self):
        self.assertAlmostEqual(safety.wrap_deg(230), -130)
        self.assertAlmostEqual(safety.wrap_deg(-190), 170)
        self.assertAlmostEqual(safety.wrap_deg(180), 180)

    def test_joint_limits(self):
        safety.check_joints([0, 15, 230, 0, 55, 90])        # J3 = -130 after wrapping
        with self.assertRaises(safety.SafetyError):
            safety.check_joints([0, 140, 0, 0, 0, 0])
        with self.assertRaises(safety.SafetyError):
            safety.check_joints([0, 0, 0])

    def test_confirm_non_tty_requires_yes(self):
        if sys.stdin.isatty():
            self.skipTest("interactive")
        with self.assertRaises(safety.SafetyError):
            safety.confirm("x", assume_yes=False)
        safety.confirm("x", assume_yes=True)


if __name__ == "__main__":
    unittest.main()
