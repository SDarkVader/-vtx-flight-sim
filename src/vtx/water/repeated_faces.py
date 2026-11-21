"""Reuse exactly repeated finite-volume neighbourhoods on an immutable chart."""
from collections import defaultdict
from copy import copy

import numpy as np


class RepeatedFaces:
    """Run the stock SWE kernel wherever an input or one of its four neighbours changed."""

    block = 32
    # Sparse path: when few cells changed, update exactly those cells (and only those)
    # with the stock face-flux function and the stock order of accumulation.
    cells_kernel = True
    cells_limit = 0.2

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
            if self.cells_kernel and np.count_nonzero(dirty) <= self.cells_limit * dirty.size:
                self._advance_cells(dt, current, dirty)
            else:
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


    def _advance_cells(self, dt, current, dirty):
        """Advance only the dirty cells, bit-identically to the stock full-grid kernel.

        Each needed face is evaluated with the stock ``_audusse_rusanov_flux_1d`` on a
        (2, K) left/right stack, and each cell sums its faces in the stock order
        (x: east -, west +; then y: north -, south +), starting from the same zero.
        Every remaining operation of the stock substep is elementwise and is repeated
        verbatim on the dirty cells. Clean cells keep their previous results.
        """
        import math

        from vtx.water.datum import RHO_AIR_ISA
        from vtx.water.shallow_water import _audusse_rusanov_flux_1d as flux

        field = self.field
        h, hu, hv, bed = current
        ny, nx = h.shape
        cells = np.flatnonzero(dirty)
        row, col = np.divmod(cells, nx)
        flat = (h.ravel(), hu.ravel(), hv.ravel(), bed.ravel())

        cfg = field.config
        g = float(cfg.g_m_s2)
        rho_w = float(cfg.rho_water_kg_m3)
        h_dry = field.h_dry

        east, west = col < nx - 1, col > 0
        north, south = row < ny - 1, row > 0
        # Each face once (indexed by its left/lower cell), each cell's state once.
        if getattr(self, '_work_size', None) != ny * nx:
            self._mark = np.zeros(ny * nx, dtype=bool)
            self._where = np.empty(ny * nx, dtype=np.intp)
            self._work_size = ny * nx
        mark, where = self._mark, self._where
        mark[cells[east]] = True
        mark[cells[west] - 1] = True
        x_faces = np.flatnonzero(mark)
        mark[x_faces] = False
        mark[cells[north]] = True
        mark[cells[south] - nx] = True
        y_faces = np.flatnonzero(mark)
        mark[y_faces] = False
        for index in (x_faces, x_faces + 1, y_faces, y_faces + nx):
            mark[index] = True
        needed = np.flatnonzero(mark)
        mark[needed] = False
        where[needed] = np.arange(needed.size)

        hh, huu, hvv, bb = (layer[needed] for layer in flat)
        wet_cells = hh > h_dry
        depth = np.maximum(hh, h_dry)
        cell = (hh, np.where(wet_cells, huu / depth, 0.0), np.where(wet_cells, hvv / depth, 0.0), bb, hh + bb)

        def faces(left, right, swap):
            a, b = where[left], where[right]
            hs, u, v, bs, eta = (np.stack((x[a], x[b])) for x in cell)
            if swap:
                u, v = v, u
            return [part[0] for part in flux(hs, u, v, bs, eta, g, h_dry, axis=0)]

        fx_h, fx_hu, fx_hv, fx_pl, fx_pr = faces(x_faces, x_faces + 1, False)
        fy_h, fy_hv, fy_hu, fy_pl, fy_pr = faces(y_faces, y_faces + nx, True)
        where[x_faces] = np.arange(x_faces.size)
        e, w = where[cells[east]], where[cells[west] - 1]
        where[y_faces] = np.arange(y_faces.size)
        n, s_ = where[cells[north]], where[cells[south] - nx]
        fe_h, fe_hu, fe_hv, fe_pl = fx_h[e], fx_hu[e], fx_hv[e], fx_pl[e]
        fw_h, fw_hu, fw_hv, fw_pr = fx_h[w], fx_hu[w], fx_hv[w], fx_pr[w]
        fn_h, fn_hv, fn_hu, fn_pl = fy_h[n], fy_hv[n], fy_hu[n], fy_pl[n]
        fs_h, fs_hv, fs_hu, fs_pr = fy_h[s_], fy_hv[s_], fy_hu[s_], fy_pr[s_]

        k = cells.size
        dh = np.zeros(k)
        dhu = np.zeros(k)
        dhv = np.zeros(k)
        inv_dx = 1.0 / field.dx
        inv_dy = 1.0 / field.dy
        dh[east] -= inv_dx * fe_h
        dh[west] += inv_dx * fw_h
        dhu[east] -= inv_dx * (fe_hu - fe_pl)
        dhu[west] += inv_dx * (fw_hu - fw_pr)
        dhv[east] -= inv_dx * fe_hv
        dhv[west] += inv_dx * fw_hv
        dh[north] -= inv_dy * fn_h
        dh[south] += inv_dy * fs_h
        dhv[north] -= inv_dy * (fn_hv - fn_pl)
        dhv[south] += inv_dy * (fs_hv - fs_pr)
        dhu[north] -= inv_dy * fn_hu
        dhu[south] += inv_dy * fs_hu

        h0, hu0, hv0 = (layer[cells] for layer in flat[:3])
        h_new = np.maximum(0.0, h0 + dt * dh)
        hu_new = hu0 + dt * dhu
        hv_new = hv0 + dt * dhv

        wet = h_new > field.h_vel_damp
        wind_spd = max(0.0, float(cfg.wind_speed_mps))
        wind_ang = math.radians(float(cfg.wind_direction_deg))
        if wind_spd > 0.05:
            c10 = (0.8 + 0.065 * wind_spd) * 1e-3
            tau_w = (RHO_AIR_ISA / rho_w) * c10 * wind_spd * wind_spd
            hu_new[wet] += dt * tau_w * math.cos(wind_ang)
            hv_new[wet] += dt * tau_w * math.sin(wind_ang)

        curr_spd = max(0.0, float(cfg.current_speed_mps))
        if curr_spd > 1e-4:
            curr_ang = math.radians(float(cfg.current_direction_deg))
            target_u = curr_spd * math.cos(curr_ang)
            target_v = curr_spd * math.sin(curr_ang)
            relax = dt * np.clip(h_new / 3.0, 0.0, 1.0) / 25.0
            hu_new += relax * (h_new * target_u - hu_new)
            hv_new += relax * (h_new * target_v - hv_new)

        friction_depth = np.maximum(h_new, field.h_vel_damp)
        u_tmp = np.where(wet, hu_new / friction_depth, 0.0)
        v_tmp = np.where(wet, hv_new / friction_depth, 0.0)
        speed = np.hypot(u_tmp, v_tmp)
        cf = (g * (field.manning_n ** 2)) / np.power(friction_depth, 4.0 / 3.0)
        fric_denom = 1.0 + dt * cf * speed
        hu_new = np.where(wet, hu_new / fric_denom, 0.0)
        hv_new = np.where(wet, hv_new / fric_denom, 0.0)

        thin = h_new <= field.h_dry
        h_new[thin] = 0.0
        hu_new[thin] = 0.0
        hv_new[thin] = 0.0

        outputs = tuple(array.copy() for array in self.results)
        for dest, values in zip(outputs, (h_new, hu_new, hv_new)):
            dest.ravel()[cells] = values
        field.h, field.hu, field.hv = outputs
