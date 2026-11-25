"""Torque backstop for joint rotations (no arm)."""
import json
import os
import tempfile
import unittest

from kinova import motion
from kinova.arms import FakeArm
from kinova.envelope import Routine, load_envelope


class TorqueWatch(unittest.TestCase):
    def run_watch(self, readings, limit=0.7):
        it, stops = iter(readings), []
        left = [len(readings)]

        def read():
            left[0] -= 1
            return next(it)
        return motion.torque_watch(read, limit, lambda: stops.append(1), lambda: left[0] <= 0, period_s=0.0), stops

    def test_trips_after_two_readings_over_the_limit(self):
        res, stops = self.run_watch([0.2, -0.3, 0.75, 0.8, 0.1])
        self.assertTrue(res["tripped"])
        self.assertEqual(stops, [1])
        self.assertAlmostEqual(res["torque_nm"], 0.8)

    def test_one_noisy_reading_does_not_trip(self):
        res, stops = self.run_watch([0.2, 0.9, 0.3, -0.75, 0.2])
        self.assertFalse(res["tripped"])
        self.assertEqual(stops, [])
        self.assertAlmostEqual(res["peak_nm"], 0.9)

    def test_negative_torque_counts_too(self):
        res, _ = self.run_watch([-0.8, -0.72])
        self.assertTrue(res["tripped"])


class EnvelopeTorque(unittest.TestCase):
    def envelope(self, **extra):
        d = {"name": "t", "box_min": [0.1, -0.2, 0.03], "box_max": [0.5, 0.3, 0.3], "max_lin_speed": 0.05,
             "max_ang_speed": 30.0, "rotate_joint": 6, "max_rotation_deg": 720.0, **extra}
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(d, f)
        f.close()
        self.addCleanup(os.remove, f.name)
        return load_envelope(f.name)

    def test_old_envelopes_have_no_limit_and_new_ones_pass_it_to_the_arm(self):
        self.assertIsNone(self.envelope().max_joint_torque_nm)
        env = self.envelope(max_joint_torque_nm=0.7)
        self.assertIn("0.70 Nm", env.summary())
        arm = FakeArm(pose={"x": 0.3, "y": 0.0, "z": 0.1, "theta_x": 180.0, "theta_y": 0.0, "theta_z": 0.0})
        r = Routine(arm, env, 0.1, 40.0, assume_yes=True)
        r.rotate(15.0, 5.0)
        self.assertEqual(arm.last_max_torque_nm, 0.7)


if __name__ == "__main__":
    unittest.main()


class RotateCap(unittest.TestCase):
    def test_per_arm_cap_from_the_environment_defaults_to_15(self):
        old = os.environ.pop("KINOVA_ROTATE_MAX_DPS", None)
        try:
            self.assertEqual(motion.rotate_max_dps(), 15.0)
            os.environ["KINOVA_ROTATE_MAX_DPS"] = "30"
            self.assertEqual(motion.rotate_max_dps(), 30.0)
        finally:
            os.environ.pop("KINOVA_ROTATE_MAX_DPS", None)
            if old is not None:
                os.environ["KINOVA_ROTATE_MAX_DPS"] = old
