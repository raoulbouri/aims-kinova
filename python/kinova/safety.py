"""Software guard-rails applied BEFORE any motion command is sent.

These do not replace the physical e-stop or the arm's own limits. They catch obviously bad
targets (typos, unit mistakes like mm-vs-m, wrong sign) before they reach the robot.

Workspace model (base frame, metres), a target p = (x, y, z) is accepted iff
    ||p||_2           <= R_MAX      (inside reachable sphere, with margin)
    z                 >= Z_MIN      (above the table surface)
    sqrt(x^2 + y^2)   >= RHO_MIN    (outside a cylinder around the base: self-collision)
Gen3 6DoF reach is 891 mm; R_MAX = 0.80 leaves ~9 cm margin for the gripper/singularity.
"""
import math
import os
import sys

R_MAX = float(os.environ.get("KINOVA_R_MAX", 0.80))
Z_MIN = float(os.environ.get("KINOVA_Z_MIN", 0.02))
RHO_MIN = float(os.environ.get("KINOVA_RHO_MIN", 0.15))
MAX_STEP = float(os.environ.get("KINOVA_MAX_STEP", 0.30))   # max Cartesian displacement per command (m)

# Gen3 6DoF joint position limits (deg); None = continuous. Verify against the user guide.
JOINT_LIMITS_DEG = [None, (-128.9, 128.9), (-147.8, 147.8), None, (-120.3, 120.3), None]


class SafetyError(RuntimeError):
    pass


def wrap_deg(a: float) -> float:
    """Map an angle to (-180, 180]. Kortex reports joints in [0, 360)."""
    a = math.fmod(a, 360.0)
    if a > 180.0:
        a -= 360.0
    elif a <= -180.0:
        a += 360.0
    return a


def check_cartesian(x, y, z, current=None):
    r = math.sqrt(x * x + y * y + z * z)
    rho = math.hypot(x, y)
    errs = []
    if r > R_MAX:
        errs.append(f"|p|={r:.3f} m > R_MAX={R_MAX}")
    if z < Z_MIN:
        errs.append(f"z={z:.3f} m < Z_MIN={Z_MIN}")
    if rho < RHO_MIN:
        errs.append(f"radial distance {rho:.3f} m < RHO_MIN={RHO_MIN}")
    if current is not None:
        d = math.dist((x, y, z), current)
        if d > MAX_STEP:
            errs.append(f"step {d:.3f} m > MAX_STEP={MAX_STEP} (split into smaller moves)")
    if errs:
        raise SafetyError("Cartesian target rejected: " + "; ".join(errs))


def check_joints(angles_deg):
    if len(angles_deg) != 6:
        raise SafetyError(f"expected 6 joint angles, got {len(angles_deg)}")
    for i, (a, lim) in enumerate(zip(angles_deg, JOINT_LIMITS_DEG)):
        if lim and not (lim[0] <= wrap_deg(a) <= lim[1]):
            raise SafetyError(f"J{i+1}={a:.1f} deg outside {lim}")


def clamp_speed(value, cap):
    return max(1e-3, min(float(value), float(cap)))


def confirm(summary: str, assume_yes: bool) -> None:
    """Every motion must be confirmed: interactively, or with --yes after a human approved it."""
    print(f"\n>>> MOTION: {summary}")
    if assume_yes:
        print(">>> --yes given, executing. Keep the e-stop within reach.")
        return
    if not sys.stdin.isatty():
        raise SafetyError("Motion needs confirmation: re-run with --yes once a human has approved it.")
    if input(">>> Type 'yes' to execute (e-stop in reach?): ").strip().lower() != "yes":
        raise SafetyError("Aborted by user.")
