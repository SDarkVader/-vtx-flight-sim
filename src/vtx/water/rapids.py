"""Analytical rapids overlay for the hybrid water field.

A world may declare rapids: a tidal race or river reach described by a downstream centreline
of stations ``[x, y, half_width_m, speed_mps]``. Like the Burgers-Rott whirlpools, the overlay
is compactly supported and adds to the solver's free surface, velocity, acceleration and
surface slope, so vessels feel it through their ordinary hydrodynamics:

- a current jet along the centreline, strongest mid-channel ((1 - q^2)^0.7 across the half
  width), with counter-current eddy lines along both banks;
- standing waves in the wave train. A surface wave is stationary in the ground frame when its
  phase speed equals the current, which in deep water gives k = g / u^2 (about 10 m at 4 m/s).
  Elevation, slope, the vertical velocity of flow over the wave and the vertical acceleration
  -u^2 k^2 eta are consistent;
- boils, small surface bumps carried downstream at about 0.8 u;
- rocks: a stagnation pillow of about u^2/2g upstream, flow deflected around the rock, and a
  wake that slows the flow and recirculates just behind it.

Everything is zero beyond the bank margin (``margin_m``) and beyond the reach ends (``reach_margin_m``,
default ``margin_m``), so worlds without rapids are unaffected.
"""
import numpy as np

G = 9.80665


def _smooth(edge0, edge1, x):
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def rapids_overlay(rapid, x, y, t, *, eta_only=False, intensity=1.0):
    """Return (eta, velocity[...,3], acceleration[...,3], slope_x, slope_y) for one rapid."""
    xa = np.asarray(x, dtype=np.float64)
    ya = np.asarray(y, dtype=np.float64)
    shape = xa.shape
    eta = np.zeros(shape)
    vel = np.zeros(shape + (3,))
    acc = np.zeros(shape + (3,))
    sx = np.zeros(shape)
    sy = np.zeros(shape)
    st = np.asarray(rapid['stations'], dtype=np.float64)
    margin = float(rapid.get('margin_m', 12.0))
    end_margin = float(rapid.get('reach_margin_m', margin))
    reach = float(st[:, 2].max()) + max(margin, end_margin)
    if (xa.size == 0 or xa.max() < st[:, 0].min() - reach or xa.min() > st[:, 0].max() + reach
            or ya.max() < st[:, 1].min() - reach or ya.min() > st[:, 1].max() + reach):
        return eta, vel, acc, sx, sy

    a = st[:-1, :2]
    d = st[1:, :2] - a
    seg_len = np.hypot(d[:, 0], d[:, 1])
    tang = d / seg_len[:, None]
    cum = np.concatenate([[0.0], np.cumsum(seg_len)])
    p = np.stack([xa.ravel(), ya.ravel()], axis=-1)
    rel = p[:, None, :] - a[None, :, :]
    raw = np.einsum('psk,sk->ps', rel, tang)
    along = np.clip(raw, 0.0, seg_len[None, :])
    foot = a[None, :, :] + along[..., None] * tang[None, :, :]
    dist2 = np.sum((p[:, None, :] - foot) ** 2, axis=-1)
    k = np.argmin(dist2, axis=1)
    idx = np.arange(p.shape[0])
    # Beyond either end the reach coordinate continues along the end segment, so the taper can act.
    a_k = along[idx, k]
    a_k = np.where((k == 0) & (raw[idx, k] < 0.0), raw[idx, k], a_k)
    last = len(seg_len) - 1
    a_k = np.where((k == last) & (raw[idx, k] > seg_len[last]), raw[idx, k], a_k)
    s = cum[k] + a_k
    T = tang[k]
    off = p - (a[k] + a_k[:, None] * T)
    n = T[:, 0] * off[:, 1] - T[:, 1] * off[:, 0]           # signed: positive to the left of the flow

    hw = np.interp(s, cum, st[:, 2])
    u = np.interp(s, cum, st[:, 3])
    du_ds = np.interp(s, cum[:-1] + seg_len / 2, np.diff(st[:, 3]) / seg_len)
    q = np.abs(n) / hw
    total = cum[-1]
    reach_taper = _smooth(-end_margin, 0.0, s) * (1.0 - _smooth(total, total + end_margin, s))
    bank_taper = 1.0 - _smooth(1.0, 1.0 + margin / np.maximum(hw, 1.0), q)
    taper = reach_taper * bank_taper * float(intensity)
    if not np.any(taper > 0):
        return eta, vel, acc, sx, sy
    core = np.power(np.clip(1.0 - q * q, 0.0, 1.0), 0.7)
    eddy = _smooth(0.70, 0.98, q) * bank_taper
    speed = u * (core - float(rapid.get('eddy_fraction', 0.25)) * eddy) * taper

    # Standing waves in the wave train.
    eta_flat = np.zeros_like(s)
    deta_ds = np.zeros_like(s)
    a_z = np.zeros_like(s)
    wave = rapid.get('waves')
    if wave:
        w0, w1, amp = float(wave['from_m']), float(wave['to_m']), float(wave['amplitude_m'])
        # The local wavenumber follows the local current, so the phase is its integral along the reach.
        grid = np.linspace(w0, w1, max(2, int((w1 - w0) / 0.5) + 1))
        k_grid = G / np.maximum(np.interp(grid, cum, st[:, 3]), 1.2) ** 2
        phase_grid = np.concatenate([[0.0], np.cumsum(0.5 * (k_grid[1:] + k_grid[:-1]) * np.diff(grid))])
        inside = (s > w0) & (s < w1)
        x01 = np.clip((s - w0) / (w1 - w0), 0.0, 1.0)
        env = np.where(inside, np.sin(np.pi * x01), 0.0)
        denv = np.where(inside, np.pi / (w1 - w0) * np.cos(np.pi * x01), 0.0)
        kw = G / np.maximum(u, 1.2) ** 2
        phase = np.interp(s, grid, phase_grid)
        scale = amp * core * taper
        eta_flat = scale * env * np.cos(phase)
        deta_ds = scale * (denv * np.cos(phase) - env * kw * np.sin(phase))
        a_z = -(speed * speed) * kw * kw * eta_flat
    # Boils drifting downstream.
    boil = float(rapid.get('boil_amplitude_m', 0.05)) * core * taper * np.sin(0.23 * (s - 0.8 * u * float(t))) * np.cos(0.41 * n + 0.6 * float(t))
    eta_flat = eta_flat + boil

    v_along = speed.copy()
    v_lat = np.zeros_like(s)
    # Rocks: pillow upstream, deflection around, wake and recirculation downstream.
    for rock in rapid.get('rocks', ()):
        rx, ry, r = float(rock['x']), float(rock['y']), max(float(rock['r_m']), 0.5)
        dx, dy = p[:, 0] - rx, p[:, 1] - ry
        near = (np.abs(dx) < 14.0 * r) & (np.abs(dy) < 14.0 * r)
        if not np.any(near):
            continue
        ra = dx * T[:, 0] + dy * T[:, 1]
        rl = -dx * T[:, 1] + dy * T[:, 0]
        u_loc = np.maximum(speed, 0.0)
        pillow = (u_loc * u_loc / (2.0 * G)) * 0.8 * np.exp(-((ra + 1.3 * r) / (0.6 * r)) ** 2) * np.exp(-(rl / r) ** 2)
        width = r * (1.0 + np.maximum(ra - r, 0.0) / (5.0 * r))
        wake = np.where(ra > r, np.exp(-(ra - r) / (4.0 * r)) * np.exp(-(rl / width) ** 2), 0.0)
        recirc = np.where(ra > r, np.exp(-(ra - r) / (1.5 * r)) * np.exp(-(rl / r) ** 2), 0.0)
        deflect = np.sign(rl) * 0.5 * np.exp(-((ra + 0.5 * r) / (1.2 * r)) ** 2) * np.exp(-(rl / (1.3 * r)) ** 2)
        mask = near.astype(float)
        eta_flat = eta_flat + pillow * mask
        v_lat = v_lat + deflect * u_loc * mask
        v_along = v_along * (1.0 - 0.9 * wake * mask) - 0.3 * u_loc * recirc * mask

    eta = eta_flat.reshape(shape)
    if eta_only:
        return eta, vel, acc, sx, sy
    N = np.stack([-T[:, 1], T[:, 0]], axis=-1)
    vxy = T * v_along[:, None] + N * v_lat[:, None]
    vel = np.concatenate([vxy, (v_along * deta_ds)[:, None]], axis=-1).reshape(shape + (3,))
    a_s = speed * du_ds * core * taper
    axy = T * a_s[:, None]
    acc = np.concatenate([axy, a_z[:, None]], axis=-1).reshape(shape + (3,))
    sx = (T[:, 0] * deta_ds).reshape(shape)
    sy = (T[:, 1] * deta_ds).reshape(shape)
    return eta, vel, acc, sx, sy
