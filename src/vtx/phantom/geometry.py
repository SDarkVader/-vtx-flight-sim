"""CAD -> MuJoCo transform and the physical/CAD name map for the Phantom.

The MuJoCo body frame IS the CAD frame: X forward, Y = CAD-RIGHT = physical LEFT (port),
Z up, right-handed, metres. CAD_TO_MUJOCO rotation is the identity; the only transform is
the spawn translation of the free joint. Pilot-facing names are physical: left = +Y.
"""
import numpy as np

CAD_TO_MUJOCO_ROTATION = np.eye(3)
PODS = ('FL', 'FR', 'RL', 'RR')            # physical order used by every control array
SIDE = {'FL': 1, 'FR': -1, 'RL': 1, 'RR': -1}   # +1 = physical left = +Y
FRONT = {'FL': True, 'FR': True, 'RL': False, 'RR': False}
CAD_POD = {'FL': 'JOINT_WHEEL_POD_FR', 'FR': 'JOINT_WHEEL_POD_FL', 'RL': 'JOINT_WHEEL_POD_RR', 'RR': 'JOINT_WHEEL_POD_RL'}
CAD_LEG = {'FL': 'JOINT_LEG_SLIDE_FR', 'FR': 'JOINT_LEG_SLIDE_FL', 'RL': 'JOINT_LEG_SLIDE_RR', 'RR': 'JOINT_LEG_SLIDE_RL'}
WING_SIDES = ('left', 'right')
WING_SIGN = {'left': 1, 'right': -1}
CAD_SIDE = {'left': 'R', 'right': 'L'}   # A9 _R objects sit at +Y = physical left
PINS = ('FRONT_OUT', 'FRONT_IN', 'REAR_OUT', 'REAR_IN')


def rot(axis, angle):
    a = np.asarray(axis, float); a = a / np.linalg.norm(a)
    x, y, z = a; c, s = np.cos(angle), np.sin(angle); C = 1 - c
    return np.array([[c + x*x*C, x*y*C - z*s, x*z*C + y*s],
                     [y*x*C + z*s, c + y*y*C, y*z*C - x*s],
                     [z*x*C - y*s, z*y*C + x*s, c + z*z*C]])


def box_inertia(m, h):
    a, b, c = (2 * np.asarray(h, float)) ** 2
    return np.diag([m * (b + c) / 12, m * (a + c) / 12, m * (a + b) / 12])


def cylinder_inertia(m, r, half, axis):
    I_ax = 0.5 * m * r * r; I_tr = m * (3 * r * r + (2 * half) ** 2) / 12
    a = np.abs(np.asarray(axis, float)); a /= np.linalg.norm(a)
    return I_tr * np.eye(3) + (I_ax - I_tr) * np.outer(a, a)
