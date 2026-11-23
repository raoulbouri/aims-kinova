"""motion.gripper returns on a stall without sending Base.Stop() (no arm, no kortex_api: both are faked)."""
import sys
import types
import unittest
from unittest import mock


def fake_base_pb2():
    m = types.ModuleType("Base_pb2")
    m.GRIPPER_POSITION = 3

    class _Fingers(list):
        def add(self):
            f = types.SimpleNamespace(finger_identifier=0, value=0.0)
            self.append(f)
            return f

    class GripperCommand:
        def __init__(self):
            self.mode = None
            self.gripper = types.SimpleNamespace(finger=_Fingers())

    class GripperRequest:
        mode = None

    m.GripperCommand, m.GripperRequest = GripperCommand, GripperRequest
    return m


class FakeBase:
    def __init__(self, positions):
        self.positions, self.i, self.stops = positions, 0, 0

    def SendGripperCommand(self, cmd):
        self.target = cmd.gripper.finger[0].value

    def GetMeasuredGripperMovement(self, req):
        v = self.positions[min(self.i, len(self.positions) - 1)]
        self.i += 1
        return types.SimpleNamespace(finger=[types.SimpleNamespace(value=v)])

    def Stop(self):
        self.stops += 1


class GripperStallTest(unittest.TestCase):
    def setUp(self):
        pkg = types.ModuleType("kortex_api"); auto = types.ModuleType("kortex_api.autogen")
        msgs = types.ModuleType("kortex_api.autogen.messages"); msgs.Base_pb2 = fake_base_pb2()
        self.mods = mock.patch.dict(sys.modules, {"kortex_api": pkg, "kortex_api.autogen": auto,
                                                  "kortex_api.autogen.messages": msgs,
                                                  "kortex_api.autogen.messages.Base_pb2": msgs.Base_pb2})
        self.mods.start()
        from kinova import motion
        self.motion = motion

    def tearDown(self):
        self.mods.stop()

    def test_stall_returns_without_stop(self):
        base = FakeBase([0.30, 0.50, 0.70, 0.712])          # closes, then sits on the knob at 0.712
        r = self.motion.gripper(types.SimpleNamespace(base=base), 1.0, timeout=3.0)
        self.assertTrue(r["ok"])
        self.assertIn("STALLED", r["event"])
        self.assertAlmostEqual(r["position"], 0.712)
        self.assertEqual(base.stops, 0)                     # a stop could cut a slow gripper short

    def test_reaching_the_target_sends_no_stop(self):
        base = FakeBase([0.40, 0.449, 0.45])
        r = self.motion.gripper(types.SimpleNamespace(base=base), 0.45, timeout=3.0)
        self.assertEqual(r["event"], "REACHED")
        self.assertEqual(base.stops, 0)


if __name__ == "__main__":
    unittest.main()
