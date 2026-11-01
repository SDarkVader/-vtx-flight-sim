"""Rotation helper that uses scipy.spatial.transform.Rotation when installed
and falls back to an exact pure-NumPy implementation in slim serverless builds."""
from __future__ import annotations
import math
import numpy as np

try:
    from scipy.spatial.transform import Rotation  # type: ignore[import-not-found]
except ImportError:
    class Rotation:  # type: ignore[no-redef]
        def __init__(self, mat):
            self._m = np.asarray(mat, dtype=float).reshape(3, 3)

        @classmethod
        def from_matrix(cls, mat):
            return cls(mat)

        @classmethod
        def from_quat(cls, quat):
            x, y, z, w = [float(v) for v in quat]
            n = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
            x, y, z, w = x / n, y / n, z / n, w / n
            return cls([
                [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
                [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
                [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)],
            ])

        @classmethod
        def from_euler(cls, seq: str, angles, degrees: bool = False):
            if seq != 'z':
                raise ValueError(f'Unsupported Euler sequence: {seq}')
            a = math.radians(float(angles)) if degrees else float(angles)
            c, s = math.cos(a), math.sin(a)
            return cls([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])

        def inv(self):
            return Rotation(self._m.T)

        def __mul__(self, other: 'Rotation'):
            return Rotation(self._m @ other._m)

        def as_euler(self, seq: str, degrees: bool = False):
            m = self._m
            if seq == 'xyz':
                sy = max(-1.0, min(1.0, float(-m[2, 0])))
                y = math.asin(sy)
                if abs(sy) < 0.9999999:
                    x = math.atan2(float(m[2, 1]), float(m[2, 2]))
                    z = math.atan2(float(m[1, 0]), float(m[0, 0]))
                else:
                    x = math.atan2(float(-m[1, 2]), float(m[1, 1]))
                    z = 0.0
                out = np.array([x, y, z], dtype=float)
            elif seq == 'XYZ':
                sy = max(-1.0, min(1.0, float(m[0, 2])))
                y = math.asin(sy)
                if abs(sy) < 0.9999999:
                    x = math.atan2(float(-m[1, 2]), float(m[2, 2]))
                    z = math.atan2(float(-m[0, 1]), float(m[0, 0]))
                else:
                    x = math.atan2(float(m[2, 1]), float(m[1, 1]))
                    z = 0.0
                out = np.array([x, y, z], dtype=float)
            else:
                raise ValueError(f'Unsupported Euler sequence: {seq}')
            return np.degrees(out) if degrees else out
