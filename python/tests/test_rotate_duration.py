"""motion.rotate_joint sends each chunk as a JOINT_CONSTRAINT_DURATION move at <= ROTATE_MAX_DPS
(no arm, no kortex_api: both are faked)."""
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from kinova import motion  # noqa: E402

DURATION, SPEED = 1, 2


def fake_base_pb2():
    m = types.ModuleType("Base_pb2")
    m.JOINT_CONSTRAINT_DURATION, m.JOINT_CONSTRAINT_SPEED = DURATION, SPEED

    class _Joints(list):
        def add(self):
            j = types.SimpleNamespace(joint_identifier=None, value=None)
            self.append(j)
            return j

    class Action:
        def __init__(self):
            self.name = self.application_data = None
            self.reach_joint_angles = types.SimpleNamespace(
                joint_angles=types.SimpleNamespace(joint_angles=_Joints()),
                constraint=types.SimpleNamespace(type=None, value=None))

    m.Action = Action
    return m


class FakeArm:
    """Joint angles in degrees; ExecuteAction jumps the arm to the target and records the action."""
    def __init__(self, angles, max_ang_speed=30.0):
        self.q = list(angles)
        self.actions = []
        self.cfg = types.SimpleNamespace(max_ang_speed=max_ang_speed)
        self.base = types.SimpleNamespace(ExecuteAction=self._execute)

    def _execute(self, action):
        self.actions.append(action)
        self.q = [j.value for j in action.reach_joint_angles.joint_angles.joint_angles]


class RotateDurationTest(unittest.TestCase):
    def setUp(self):
        msgs = types.ModuleType("kortex_api.autogen.messages")
        msgs.Base_pb2 = fake_base_pb2()
        self.mods = mock.patch.dict(sys.modules, {
            "kortex_api": types.ModuleType("kortex_api"),
            "kortex_api.autogen": types.ModuleType("kortex_api.autogen"),
            "kortex_api.autogen.messages": msgs, "kortex_api.autogen.messages.Base_pb2": msgs.Base_pb2})
        self.mods.start()
        self.addCleanup(self.mods.stop)
        # _run would talk to the arm (servoing mode, notifications): run the send directly instead.
        self.timeouts = []

        def run(k, send, timeout=motion.ACTION_TIMEOUT_S):
            self.timeouts.append(timeout)
            send()
            return {"ok": True, "event": "ACTION_END"}

        p = mock.patch.object(motion, "_run", side_effect=run)
        p.start()
        self.addCleanup(p.stop)
        # The fake arm moves instantly; the "finished too fast" check is covered in test_routine.py.
        f = mock.patch.object(motion, "ROTATE_MIN_TIME_FRAC", 0.0)
        f.start()
        self.addCleanup(f.stop)
        q = mock.patch.object(motion.state, "joint_angles", side_effect=lambda k: list(k.q))
        q.start()
        self.addCleanup(q.stop)

    def chunks(self, arm):
        return [(a.reach_joint_angles.constraint.type, a.reach_joint_angles.constraint.value,
                 a.reach_joint_angles.joint_angles.joint_angles[5].value) for a in arm.actions]

    def test_duration_constraint_and_speed_cap(self):
        arm = FakeArm([0, 15, -130, 0, 55, 90])
        r = motion.rotate_joint(arm, 5, 240.0)                 # no speed given: .env cap 30 -> clamped to 15
        self.assertTrue(r["ok"])
        c = self.chunks(arm)
        self.assertEqual(len(c), 2)                            # 240 deg = two 120 deg chunks
        for typ, dur, _ in c:
            self.assertEqual(typ, DURATION)                    # never JOINT_CONSTRAINT_SPEED (aborts on 2.5.2)
            self.assertAlmostEqual(dur, 120.0 / motion.ROTATE_MAX_DPS)
        self.assertAlmostEqual(c[0][2], -150.0)                # 90 + 120 wraps to -150
        self.assertAlmostEqual(c[1][2], -30.0)

    def test_caller_cannot_exceed_cap(self):
        arm = FakeArm([0, 15, -130, 0, 55, 0])
        motion.rotate_joint(arm, 5, 60.0, speed_dps=30.0)
        self.assertAlmostEqual(self.chunks(arm)[0][1], 60.0 / motion.ROTATE_MAX_DPS)

    def test_slower_request_is_kept(self):
        arm = FakeArm([0, 15, -130, 0, 55, 0])
        motion.rotate_joint(arm, 5, -60.0, speed_dps=10.0)
        self.assertAlmostEqual(self.chunks(arm)[0][1], 6.0)

    def test_short_chunk_gets_minimum_duration(self):
        arm = FakeArm([0, 15, -130, 0, 55, 0])
        motion.rotate_joint(arm, 5, 5.0)                       # 5 deg at 15 deg/s = 0.33 s -> 1 s minimum
        self.assertAlmostEqual(self.chunks(arm)[0][1], motion.ROTATE_MIN_CHUNK_S)
        self.assertGreater(self.timeouts[0], motion.ROTATE_MIN_CHUNK_S)  # wait covers the stretched move

    def test_other_joints_are_held(self):
        arm = FakeArm([10, 15, -130, 20, 55, 0])
        motion.rotate_joint(arm, 5, 30.0)
        sent = [j.value for j in arm.actions[0].reach_joint_angles.joint_angles.joint_angles]
        self.assertEqual(sent[:5], [10, 15, -130, 20, 55])


if __name__ == "__main__":
    unittest.main()
