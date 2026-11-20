"""Reuse exactly repeated finite-volume neighbourhoods on an immutable chart."""
from collections import defaultdict
from copy import copy

import numpy as np


class RepeatedFaces:
    """Run the stock SWE kernel wherever an input or one of its four neighbours changed."""

    block = 32

    def __init__(self, field):
        self.field = field
        self.stock = type(field)._advance_substep
        self.inputs = None
        self.results = None
        self.signature = None

    def __call__(self, dt):
        field = self.field
        current = (field.h, field.hu, field.hv, field.bed)
        cfg = field.config
        signature = (dt, field.dx, field.dy, field.manning_n, field.h_dry,
                     field.h_vel_damp, cfg.g_m_s2, cfg.rho_water_kg_m3,
                     cfg.wind_speed_mps, cfg.wind_direction_deg,
                     cfg.current_speed_mps, cfg.current_direction_deg, field.h.shape)
        previous = self.inputs
        self.inputs = tuple(array.copy() for array in current)
        if previous is None or self.signature != signature:
            self.stock(field, dt)
        else:
            changed = np.zeros(field.h.shape, dtype=bool)
            for old, new in zip(previous, current):
                changed |= old.view(np.uint64) != new.view(np.uint64)
            dirty = changed.copy()
            dirty[1:] |= changed[:-1]
            dirty[:-1] |= changed[1:]
            dirty[:, 1:] |= changed[:, :-1]
            dirty[:, :-1] |= changed[:, 1:]
            self._advance_changed(dt, current, dirty)
        self.signature = signature
        # Vessel impulses can mutate the field between substeps.
        self.results = tuple(array.copy() for array in (field.h, field.hu, field.hv))

    def _advance_changed(self, dt, current, dirty):
        field = self.field
        ny, nx = dirty.shape
        rows = np.arange(0, ny, self.block)
        cols = np.arange(0, nx, self.block)
        active = np.logical_or.reduceat(np.logical_or.reduceat(dirty, rows, axis=0), cols, axis=1)
        if np.count_nonzero(active) > .54 * active.size:
            self.stock(field, dt)
            return

        outputs = tuple(array.copy() for array in self.results)
        patch = copy(field)
        groups = defaultdict(list)
        for y, row in zip(rows, active):
            y1 = min(y + self.block, ny)
            edges = np.flatnonzero(np.diff(np.r_[False, row, False]))
            for start, stop in zip(edges[::2], edges[1::2]):
                x, x1 = start * self.block, min(stop * self.block, nx)
                top, bottom = max(0, y-1), min(ny, y1+1)
                left, right = max(0, x-1), min(nx, x1+1)
                # Interior strips of equal width share a kernel dispatch. A one-cell
                # halo hides each packing seam. A true Y wall needs its own dispatch.
                key = (right-left, y if y == 0 or y1 == ny else -1)
                if key[1] >= 0:
                    key += (x,)
                groups[key].append((top, bottom, left, right, y, y1, x, x1))

        for group in groups.values():
            halos = [np.s_[top:bottom, left:right] for top, bottom, left, right, *_ in group]
            parts = [(a[halos[0]] if len(halos) == 1 else np.concatenate([a[s] for s in halos]))
                     for a in current]
            patch.h, patch.hu, patch.hv, patch.bed = parts
            self.stock(patch, dt)
            offset = 0
            for top, bottom, left, _, y, y1, x, x1 in group:
                core = np.s_[offset+y-top:offset+y1-top, x-left:x1-left]
                for dest, result in zip(outputs, (patch.h, patch.hu, patch.hv)):
                    dest[y:y1, x:x1] = result[core]
                offset += bottom - top
        field.h, field.hu, field.hv = outputs
