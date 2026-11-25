"""Generate the Ricochet RC-01 19-DOF / 9-Control-Surface & Telemetry-Only AI Maneuverability Diagram.

Reads authoritative hinge coordinates, dimensions, and limits directly from
`src/vtx/ricochet/concept_a_builder.py` and `inputs/ricochet_profiles/*.json`
and outputs a publication-grade vector SVG at:
    docs/ricochet/complete_model/ricochet_control_surfaces_diagram.svg

Usage (zero arguments):
    python docs/ricochet/complete_model/generate_control_surfaces_diagram.py
"""
from __future__ import annotations

import ast
import json
import math
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from xml.sax.saxutils import escape

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


def _load_profile_json(filename: str) -> dict:
    return json.loads((REPO_ROOT / 'inputs' / 'ricochet_profiles' / filename).read_text(encoding='utf-8'))


def _load_vtx_hinge_constants(opt1: dict) -> dict[str, tuple[float, float, float]]:
    """Read authoritative VTX hinge coordinates from concept_a_builder.py (stdlib fallback if numpy absent)."""
    try:
        sys.path.insert(0, str(REPO_ROOT / 'src'))
        from vtx.ricochet import concept_a_builder as cab  # type: ignore[import-not-found]
        return {
            'S': tuple(float(x) for x in cab.SPONSON_MOUNT_CONCEPT_A_VTX),
            'F': tuple(float(x) for x in cab.FAN_CENTER_PORT_VTX),
            'AIL_P': tuple(float(x) for x in cab.AILERON_HINGE_PORT_VTX),
            'ELEV': tuple(float(x) for x in cab.ELEVATOR_HINGE_VTX),
            'RUD': tuple(float(x) for x in cab.RUDDER_HINGE_VTX),
            'REV_P': tuple(float(x) for x in cab.REVERSE_BUCKET_HINGE_PORT_VTX),
        }
    except ImportError:
        src_text = (REPO_ROOT / 'src' / 'vtx' / 'ricochet' / 'concept_a_builder.py').read_text(encoding='utf-8')
        tree = ast.parse(src_text)
        literals: dict[str, tuple[float, float, float]] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name in ('SPONSON_MOUNT_CONCEPT_A_VTX', 'FAN_CENTER_PORT_VTX', 'ELEVATOR_HINGE_VTX', 'REVERSE_BUCKET_HINGE_PORT_VTX'):
                    literals[name] = tuple(float(x) for x in ast.literal_eval(node.value))
        mounts = opt1.get('actuator_mounts_vtx_m', {})
        return {
            'S': literals['SPONSON_MOUNT_CONCEPT_A_VTX'],
            'F': literals['FAN_CENTER_PORT_VTX'],
            'AIL_P': tuple(float(x) for x in mounts['aileron_port_servo']),
            'ELEV': literals['ELEVATOR_HINGE_VTX'],
            'RUD': tuple(float(x) for x in mounts['rudder_servo']),
            'REV_P': literals['REVERSE_BUCKET_HINGE_PORT_VTX'],
        }


def _poly(pts: list[tuple[float, float]], **attrs: str) -> str:
    pstr = ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts)
    astr = ' '.join(f'{k.replace("_", "-")}="{escape(str(v))}"' for k, v in attrs.items())
    return f'<polygon points="{pstr}" {astr}/>'


def _line(x1: float, y1: float, x2: float, y2: float, **attrs: str) -> str:
    astr = ' '.join(f'{k.replace("_", "-")}="{escape(str(v))}"' for k, v in attrs.items())
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" {astr}/>'


def _rect(x: float, y: float, w: float, h: float, **attrs: str) -> str:
    astr = ' '.join(f'{k.replace("_", "-")}="{escape(str(v))}"' for k, v in attrs.items())
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" {astr}/>'


def _text(x: float, y: float, content: str, **attrs: str) -> str:
    astr = ' '.join(f'{k.replace("_", "-")}="{escape(str(v))}"' for k, v in attrs.items())
    return f'<text x="{x:.1f}" y="{y:.1f}" {astr}>{escape(content)}</text>'


def _badge(cx: float, cy: float, num: str, fill: str, r: float = 11.5) -> str:
    return (
        f'<g>'
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" stroke="#0b1017" stroke-width="2"/>'
        f'<text x="{cx:.1f}" y="{cy + 4.2:.1f}" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" '
        f'font-size="11.5" font-weight="800" fill="#0b1017">{escape(num)}</text>'
        f'</g>'
    )


def _callout(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    num: str,
    title: str,
    sub: str,
    color: str,
    align: str = 'start',
    elbow_x: float | None = None,
) -> str:
    parts = []
    if elbow_x is not None:
        parts.append(
            f'<polyline points="{ax:.1f},{ay:.1f} {elbow_x:.1f},{by:.1f} {bx:.1f},{by:.1f}" '
            f'fill="none" stroke="{color}" stroke-width="1.5" stroke-opacity="0.85"/>'
        )
    else:
        parts.append(_line(ax, ay, bx, by, stroke=color, stroke_width='1.5', stroke_opacity='0.85'))
    parts.append(f'<circle cx="{ax:.1f}" cy="{ay:.1f}" r="3.2" fill="{color}"/>')
    tx = bx + (18 if align == 'start' else -18)
    badge_x = bx + (3 if align == 'start' else -3)
    parts.append(_badge(badge_x, by, num, color, r=10.5))
    parts.append(_text(
        tx, by - 2.0, title,
        text_anchor=align, font_family='Segoe UI, Arial, sans-serif',
        font_size='12', font_weight='700', fill='#f1f5f9',
    ))
    parts.append(_text(
        tx, by + 12.5, sub,
        text_anchor=align, font_family='Consolas, Segoe UI, monospace',
        font_size='10.2', fill='#94a3b8',
    ))
    return '\n'.join(parts)


def build_svg() -> str:
    opt1 = _load_profile_json('rc01_planing_3pt_v1.json')
    opt2 = _load_profile_json('rc01_hydrofoil_ski_v1.json')

    # Exact VTX constants (from concept_a_builder.py / profile mounts)
    c = _load_vtx_hinge_constants(opt1)
    S = c['S']          # (-0.34, 3.80, 0.48)
    F = c['F']          # (-2.05, 0.78, 1.56)
    AIL_P = c['AIL_P']
    ELEV = c['ELEV']    # (-3.14, 0.0, 2.302)
    RUD = c['RUD']      # (-2.59, 0.0, 1.58)
    REV_P = c['REV_P']  # (-2.33, 0.78, 1.56)

    W, H = 1920, 1340
    C_BG = '#0b1017'
    C_PANEL = '#121923'
    C_SUB = '#17202c'
    C_BORDER = '#273549'
    C_GOLD = '#f4b41a'
    C_CYAN = '#38bdf8'
    C_GREEN = '#22c55e'
    C_ORANGE = '#fb923c'
    C_RED = '#f87171'
    C_PURPLE = '#c084fc'
    C_MUTED = '#94a3b8'
    C_TEXT = '#e2e8f0'

    el: list[str] = []
    el.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
    el.append('''<defs>
  <linearGradient id="hdrGrad" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="#111a26"/>
    <stop offset="60%" stop-color="#162232"/>
    <stop offset="100%" stop-color="#1a2430"/>
  </linearGradient>
  <linearGradient id="hullGrad" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="#222d3d"/>
    <stop offset="55%" stop-color="#2d3c50"/>
    <stop offset="100%" stop-color="#3a4c64"/>
  </linearGradient>
  <linearGradient id="waterGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#0ea5e9" stop-opacity="0.22"/>
    <stop offset="100%" stop-color="#0369a1" stop-opacity="0.06"/>
  </linearGradient>
  <marker id="arrCyan" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M0,1 L9,5 L0,9 z" fill="#38bdf8"/>
  </marker>
  <marker id="arrGold" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M0,1 L9,5 L0,9 z" fill="#f4b41a"/>
  </marker>
  <marker id="arrGreen" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M0,1 L9,5 L0,9 z" fill="#22c55e"/>
  </marker>
  <marker id="arrOrange" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M0,1 L9,5 L0,9 z" fill="#fb923c"/>
  </marker>
  <marker id="arrRed" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M0,1 L9,5 L0,9 z" fill="#f87171"/>
  </marker>
</defs>''')

    # Background
    el.append(_rect(0, 0, W, H, fill=C_BG))

    # Header band
    el.append(_rect(0, 0, W, 84, fill='url(#hdrGrad)'))
    el.append(_line(0, 84, W, 84, stroke=C_GOLD, stroke_width='2.5'))
    el.append(_rect(24, 18, 8, 48, rx='3', fill=C_GOLD))
    el.append(_text(
        46, 42, 'VTX RICOCHET RC-01 — 19-DOF / 9-CONTROL-SURFACE & TELEMETRY-ONLY MANEUVERABILITY',
        font_family='Segoe UI, Arial, sans-serif', font_size='23', font_weight='800', fill='#f8fafc', letter_spacing='0.5',
    ))
    el.append(_text(
        46, 65,
        'Human Helm UI + Telemetry-Only AI Pilot (/api/observe -> /api/action)  |  5-Mode Stability & Trim ECU  |  Real Volz / Exlar / EMRAX 228 Actuators  |  Option 1 (RC01-P1-R1) & Option 2 (RC01-H1-R1)',
        font_family='Segoe UI, Arial, sans-serif', font_size='12.5', fill=C_MUTED,
    ))
    # Frame badge top-right
    el.append(_rect(1558, 16, 338, 52, rx='8', fill='#0d1520', stroke=C_BORDER, stroke_width='1.2'))
    el.append(_text(1574, 37, 'VTX BODY FRAME (+X FWD · +Y PORT · +Z UP)', font_family='Consolas, monospace', font_size='11.5', font_weight='700', fill=C_CYAN))
    el.append(_text(1574, 56, '400 Hz MuJoCo · 19 DOFs (nq=20, njnt=14, nu=11)', font_family='Consolas, monospace', font_size='11', fill=C_MUTED))

    # =========================================================================
    # PANEL A: PHYSICAL CONTROL-SURFACE LAYOUT (TOP PLAN + SIDE ELEVATION)
    # =========================================================================
    el.append(_rect(24, 98, 1872, 608, rx='12', fill=C_PANEL, stroke=C_BORDER, stroke_width='1.5'))
    el.append(_text(44, 126, 'A. PHYSICAL GEOMETRY OF ALL 9 ACTIVE CONTROL SURFACES + 2 DUCTED FANS + 2 PASSIVE SPONSON FLEX DOFs',
                    font_family='Segoe UI, Arial, sans-serif', font_size='14.5', font_weight='800', fill=C_GOLD, letter_spacing='0.4'))

    # Color legend in Panel A header
    legend_items = [
        (C_CYAN, 'Aero Surfaces [1-4]', 138),
        (C_RED, 'Reverse Buckets [5-6]', 152),
        (C_ORANGE, 'Main Skis Opt 1 / Opt 2 [7-8]', 188),
        (C_GREEN, 'Aft Trim Ski [9]', 120),
        (C_GOLD, 'Twin EMRAX Fans', 132),
        (C_PURPLE, 'Passive Sponson Flex', 148),
    ]
    lx = 995
    for col, lbl, step_w in legend_items:
        el.append(_rect(lx, 114, 11, 11, rx='2.5', fill=col))
        el.append(_text(lx + 16, 124, lbl, font_family='Segoe UI, Arial, sans-serif', font_size='10.6', fill=C_TEXT))
        lx += step_w

    # --- SUB-PANEL A1: TOP PLAN VIEW ---
    el.append(_rect(40, 140, 1004, 550, rx='8', fill=C_SUB, stroke=C_BORDER, stroke_width='1'))
    el.append(_text(56, 162, 'TOP PLAN VIEW (TO SCALE FROM VTX GEOMETRY)  ·  +X FORWARD (RIGHT)  ·  +Y PORT (UP)',
                    font_family='Consolas, monospace', font_size='11.5', font_weight='700', fill=C_CYAN))

    # Coordinate transform for Top Plan View: x_vtx in [-3.8, +4.2], y_vtx in [-4.8, +4.8]
    # Center around pixel (538, 418), scale = 50 px/m
    cx_t, cy_t, sc_t = 538.0, 418.0, 49.0

    def pt_top(xv: float, yv: float) -> tuple[float, float]:
        return (cx_t + xv * sc_t, cy_t - yv * sc_t)

    # Subtle 1 m grid
    for gx in range(-4, 5):
        px, _ = pt_top(gx, 0)
        el.append(_line(px, 174, px, 676, stroke='#1f2c3d', stroke_width='1', stroke_dasharray='3,4'))
    for gy in range(-4, 5, 2):
        _, py = pt_top(0, gy)
        el.append(_line(52, py, 1030, py, stroke='#1f2c3d', stroke_width='1', stroke_dasharray='3,4'))
    # Centerline
    el.append(_line(52, cy_t, 1030, cy_t, stroke='#334155', stroke_width='1.1', stroke_dasharray='8,5'))

    # Wings (exact Concept A chord & sweep: |y| in [0.52, 4.64])
    def _wing_le_te(y_abs: float) -> tuple[float, float]:
        t = (y_abs - 0.52) / 4.12
        chord = 2.02 * (1.0 - 0.45 * t)
        x_le = 1.15 - 1.07 * t
        return x_le, x_le - chord

    for sy in (1.0, -1.0):
        xle0, xte0 = _wing_le_te(0.52)
        xle1, xte1 = _wing_le_te(4.64)
        wing_pts = [pt_top(xle0, sy * 0.52), pt_top(xle1, sy * 4.64), pt_top(xte1, sy * 4.64), pt_top(xte0, sy * 0.52)]
        el.append(_poly(wing_pts, fill='#243245', stroke='#64748b', stroke_width='1.4'))
        # Winglet tip strip
        wt_pts = [pt_top(xle1, sy * 4.64), pt_top(xle1, sy * 4.74), pt_top(xte1, sy * 4.74), pt_top(xte1, sy * 4.64)]
        el.append(_poly(wt_pts, fill='#334155', stroke='#94a3b8', stroke_width='1'))

        # Ailerons [1] Port, [2] Stbd: |y| in [2.10, 4.24], 73%-100% chord
        ale0, ate0 = _wing_le_te(2.10)
        ale1, ate1 = _wing_le_te(4.24)
        ah0 = ale0 - 0.73 * (ale0 - ate0)
        ah1 = ale1 - 0.73 * (ale1 - ate1)
        ail_pts = [pt_top(ah0, sy * 2.10), pt_top(ah1, sy * 4.24), pt_top(ate1, sy * 4.24), pt_top(ate0, sy * 2.10)]
        el.append(_poly(ail_pts, fill='#0284c7', fill_opacity='0.65', stroke=C_CYAN, stroke_width='2'))
        # Hinge line
        hx0, hy0 = pt_top(ah0, sy * 2.10)
        hx1, hy1 = pt_top(ah1, sy * 4.24)
        el.append(_line(hx0, hy0, hx1, hy1, stroke='#e0f2fe', stroke_width='1.6', stroke_dasharray='4,2'))

        # Outboard Sponson pods at (-0.34, +/-3.80)
        sp_pts = [
            pt_top(S[0] + 1.35, sy * (S[1] - 0.14)),
            pt_top(S[0] + 1.65, sy * S[1]),
            pt_top(S[0] + 1.35, sy * (S[1] + 0.14)),
            pt_top(S[0] - 1.30, sy * (S[1] + 0.22)),
            pt_top(S[0] - 1.30, sy * (S[1] - 0.22)),
        ]
        el.append(_poly(sp_pts, fill='#1e293b', stroke=C_PURPLE, stroke_width='1.7'))

        # Option 1 Main Planing Ski [7/8] (solid orange)
        s1 = opt1['skis']
        px1 = S[0] + s1['pivot_in_sponson_m'][0]
        py1 = sy * (S[1] + s1['pivot_in_sponson_m'][1])
        L1, B1, a1 = s1['length_m'], s1['beam_m'], s1['hinge_from_trailing_edge_m']
        ski1_pts = [
            pt_top(px1 + (L1 - a1), py1 - 0.5 * B1),
            pt_top(px1 + (L1 - a1), py1 + 0.5 * B1),
            pt_top(px1 - a1, py1 + 0.5 * B1),
            pt_top(px1 - a1, py1 - 0.5 * B1),
        ]
        el.append(_poly(ski1_pts, fill=C_ORANGE, fill_opacity='0.38', stroke=C_ORANGE, stroke_width='2'))
        # Ski hinge line
        sh0, sy0 = pt_top(px1, py1 - 0.5 * B1)
        sh1, sy1 = pt_top(px1, py1 + 0.5 * B1)
        el.append(_line(sh0, sy0, sh1, sy1, stroke='#ffedd5', stroke_width='1.5', stroke_dasharray='3,2'))

        # Option 2 Hydrofoil Ski overlay (dashed amber-orange)
        s2 = opt2['skis']
        px2 = S[0] + s2['pivot_in_sponson_m'][0]
        py2 = sy * (S[1] + s2['pivot_in_sponson_m'][1])
        L2, B2, a2 = s2['length_m'], s2['beam_m'], s2['hinge_from_trailing_edge_m']
        ski2_pts = [
            pt_top(px2 + (L2 - a2), py2 - 0.5 * B2),
            pt_top(px2 + (L2 - a2), py2 + 0.5 * B2),
            pt_top(px2 - a2, py2 + 0.5 * B2),
            pt_top(px2 - a2, py2 - 0.5 * B2),
        ]
        el.append(_poly(ski2_pts, fill='none', stroke='#fde047', stroke_width='1.6', stroke_dasharray='5,3'))

    # Main hull outline (ogive bow to transom)
    hull_profile = [
        (3.65, 0.0), (3.15, 0.28), (2.30, 0.52), (1.10, 0.64),
        (-0.80, 0.62), (-1.95, 0.52), (-2.38, 0.40),
        (-2.38, -0.40), (-1.95, -0.52), (-0.80, -0.62),
        (1.10, -0.64), (2.30, -0.52), (3.15, -0.28),
    ]
    el.append(_poly([pt_top(x, y) for x, y in hull_profile], fill='url(#hullGrad)', stroke='#94a3b8', stroke_width='1.8'))
    # Canopy glass teardrop
    canopy_pts = [
        (2.45, 0.0), (1.85, 0.36), (0.60, 0.42), (-0.55, 0.28), (-0.95, 0.0),
        (-0.55, -0.28), (0.60, -0.42), (1.85, -0.36),
    ]
    el.append(_poly([pt_top(x, y) for x, y in canopy_pts], fill='#0ea5e9', fill_opacity='0.26', stroke='#7dd3fc', stroke_width='1.2'))

    # Aft trim ski [9] (Opt 1 solid green + Opt 2 dashed lime)
    a1_cfg = opt1['aft_ski']
    ap1 = a1_cfg['pivot_in_airframe_m']
    La1, Ba1, aa1 = a1_cfg['length_m'], a1_cfg['beam_m'], a1_cfg['hinge_from_trailing_edge_m']
    aft1_pts = [
        pt_top(ap1[0] + (La1 - aa1), -0.5 * Ba1),
        pt_top(ap1[0] + (La1 - aa1), +0.5 * Ba1),
        pt_top(ap1[0] - aa1, +0.5 * Ba1),
        pt_top(ap1[0] - aa1, -0.5 * Ba1),
    ]
    el.append(_poly(aft1_pts, fill=C_GREEN, fill_opacity='0.40', stroke=C_GREEN, stroke_width='2'))

    a2_cfg = opt2['aft_ski']
    ap2 = a2_cfg['pivot_in_airframe_m']
    La2, Ba2, aa2 = a2_cfg['length_m'], a2_cfg['beam_m'], a2_cfg['hinge_from_trailing_edge_m']
    aft2_pts = [
        pt_top(ap2[0] + (La2 - aa2), -0.5 * Ba2),
        pt_top(ap2[0] + (La2 - aa2), +0.5 * Ba2),
        pt_top(ap2[0] - aa2, +0.5 * Ba2),
        pt_top(ap2[0] - aa2, -0.5 * Ba2),
    ]
    el.append(_poly(aft2_pts, fill='none', stroke='#86efac', stroke_width='1.5', stroke_dasharray='4,3'))

    # Twin Ducted Fans & Reverse Buckets [5/6]
    for sy in (1.0, -1.0):
        fy = sy * F[1]
        fx0, fy0 = pt_top(F[0] - 0.30, fy + 0.45)
        fx1, fy1 = pt_top(F[0] + 0.35, fy - 0.45)
        el.append(_rect(min(fx0, fx1), min(fy0, fy1), abs(fx1 - fx0), abs(fy1 - fy0),
                        rx='5', fill='#334155', stroke=C_GOLD, stroke_width='2'))
        # Reverse bucket [5/6] aft of duct exit
        bx0, by0 = pt_top(REV_P[0] - 0.34, fy + 0.42)
        bx1, by1 = pt_top(REV_P[0] + 0.04, fy - 0.42)
        el.append(_rect(min(bx0, bx1), min(by0, by1), abs(bx1 - bx0), abs(by1 - by0),
                        rx='4', fill=C_RED, fill_opacity='0.48', stroke=C_RED, stroke_width='1.8'))

    # T-Tail horizontal stabilizer & Elevator [3] & Rudder [4]
    ht_pts = [
        pt_top(-2.72, 1.38), pt_top(-3.14, 1.38), pt_top(-3.14, -1.38), pt_top(-2.72, -1.38),
    ]
    el.append(_poly(ht_pts, fill='#2b3b4e', stroke='#94a3b8', stroke_width='1.4'))
    el_pts = [
        pt_top(ELEV[0], 1.35), pt_top(ELEV[0] - 0.42, 1.35),
        pt_top(ELEV[0] - 0.42, -1.35), pt_top(ELEV[0], -1.35),
    ]
    el.append(_poly(el_pts, fill='#0284c7', fill_opacity='0.70', stroke=C_CYAN, stroke_width='2'))
    # Rudder vertical trace along centerline
    rx0, ry0 = pt_top(RUD[0] + 0.08, 0.08)
    rx1, ry1 = pt_top(RUD[0] - 0.56, -0.08)
    el.append(_rect(min(rx0, rx1), min(ry0, ry1), abs(rx1 - rx0), abs(ry1 - ry0),
                    rx='3', fill='#38bdf8', stroke='#e0f2fe', stroke_width='1.6'))

    # CG Marker (measured 19-DOF MuJoCo CG: x=0.325 m, z=0.693 m for RC01-P1-R1 / RC01-H1-R1)
    cgx, cgy = pt_top(0.325, 0.0)
    el.append(f'<circle cx="{cgx:.1f}" cy="{cgy:.1f}" r="6.5" fill="none" stroke="{C_GOLD}" stroke-width="2"/>')
    el.append(f'<path d="M{cgx:.1f},{cgy - 6.5:.1f} A6.5,6.5 0 0,1 {cgx + 6.5:.1f},{cgy:.1f} L{cgx:.1f},{cgy:.1f} Z" fill="{C_GOLD}"/>')
    el.append(f'<path d="M{cgx:.1f},{cgy + 6.5:.1f} A6.5,6.5 0 0,1 {cgx - 6.5:.1f},{cgy:.1f} L{cgx:.1f},{cgy:.1f} Z" fill="{C_GOLD}"/>')
    el.append(_line(cgx + 5, cgy - 6, cgx + 36, cgy - 46, stroke=C_GOLD, stroke_width='1.3', stroke_opacity='0.85'))
    el.append(_text(cgx + 40, cgy - 43, 'CG (x=0.33m, z=0.69m)', font_family='Consolas, monospace', font_size='10.2', font_weight='700', fill=C_GOLD))

    # Clean non-overlapping callouts around Top Plan View
    # Port side (top half)
    p_s7 = pt_top(S[0] + opt1['skis']['pivot_in_sponson_m'][0], S[1])
    el.append(_callout(p_s7[0], p_s7[1], 742, 198, '7', 'Port Main Hydro-Ski', 'Exlar GSX30 · 1,416 Nm · Coll+Diff', C_ORANGE, align='start', elbow_x=706))
    p_a1 = pt_top(AIL_P[0], AIL_P[1])
    el.append(_callout(p_a1[0], p_a1[1], 742, 248, '1', 'Port Aileron [-25, +25 deg]', 'Volz DA 30-HT-D · +cmd -> TE down', C_CYAN, align='start', elbow_x=665))
    p_sp = pt_top(S[0] - 0.8, S[1])
    el.append(_callout(p_sp[0], p_sp[1], 320, 198, 'S', 'Sponson Flex Z (+/-0.06m)', '2 Passive DOFs + 6-Axis Sensors', C_PURPLE, align='end', elbow_x=370))
    p_rb5 = pt_top(REV_P[0] - 0.15, REV_P[1])
    el.append(_callout(p_rb5[0], p_rb5[1], 320, 266, '5', 'Port Reverse Bucket [0-85 deg]', 'Volz DA 58-D + Lock · Braking', C_RED, align='end', elbow_x=378))
    p_el = pt_top(ELEV[0] - 0.20, 1.15)
    el.append(_callout(p_el[0], p_el[1], 320, 326, '3', 'T-Tail Elevator [-20, +20 deg]', 'Volz DA 30-HT-D · +cmd -> Nose Up', C_CYAN, align='end', elbow_x=348))
    p_rd = pt_top(RUD[0] - 0.25, 0.0)
    el.append(_callout(p_rd[0], p_rd[1], 320, 418, '4', 'Rudder [-30, +30 deg]', 'Volz DA 58-D · Cove Clear · +Port', C_CYAN, align='end'))

    # Starboard side (bottom half)
    p_rb6 = pt_top(REV_P[0] - 0.15, -REV_P[1])
    el.append(_callout(p_rb6[0], p_rb6[1], 320, 512, '6', 'Stbd Reverse Bucket [0-85 deg]', 'Volz DA 58-D + Lock · Braking', C_RED, align='end', elbow_x=378))
    p_af9 = pt_top(ap1[0], -0.18)
    el.append(_callout(p_af9[0], p_af9[1], 320, 574, '9', 'Aft Stern Trim Ski/Foil', 'Volz DA 58-D · +cmd -> Nose Down', C_GREEN, align='end', elbow_x=435))
    p_fn = pt_top(F[0] + 0.10, -F[1])
    el.append(_callout(p_fn[0], p_fn[1], 320, 636, 'F', 'Twin EMRAX 228 Fans', 'Throttle [0..1] + Diff Thrust [-1..+1]', C_GOLD, align='end', elbow_x=418))

    p_a2 = pt_top(AIL_P[0], -AIL_P[1])
    el.append(_callout(p_a2[0], p_a2[1], 742, 572, '2', 'Stbd Aileron [-25, +25 deg]', 'Volz DA 30-HT-D · +cmd -> TE up', C_CYAN, align='start', elbow_x=665))
    p_s8 = pt_top(S[0] + opt1['skis']['pivot_in_sponson_m'][0], -S[1])
    el.append(_callout(p_s8[0], p_s8[1], 742, 632, '8', 'Stbd Main Hydro-Ski', 'Exlar GSX30 · 1,416 Nm · Coll-Diff', C_ORANGE, align='start', elbow_x=706))

    # Forward arrow on Plan View
    el.append(_line(845, 418, 975, 418, stroke=C_GOLD, stroke_width='2.2', marker_end='url(#arrGold)'))
    el.append(_text(910, 408, '+X FORWARD', text_anchor='middle', font_family='Consolas, monospace', font_size='11', font_weight='700', fill=C_GOLD))

    # --- SUB-PANEL A2: SIDE ELEVATION VIEW ---
    el.append(_rect(1058, 140, 822, 550, rx='8', fill=C_SUB, stroke=C_BORDER, stroke_width='1'))
    el.append(_text(1074, 162, 'SIDE ELEVATION (STARBOARD VIEW)  ·  +X FORWARD (RIGHT)  ·  +Z UP',
                    font_family='Consolas, monospace', font_size='11.5', font_weight='700', fill=C_CYAN))

    # Side transform: x_vtx in [-3.8, +4.0], z_vtx in [-0.7, +2.7]
    cx_s, cz_s, sc_s = 1465.0, 515.0, 92.0

    def pt_side(xv: float, zv: float) -> tuple[float, float]:
        return (cx_s + xv * sc_s, cz_s - zv * sc_s)

    # Waterline band (z = 0.56 m calm static draft)
    wl_y = pt_side(0.0, 0.56)[1]
    el.append(_rect(1070, wl_y, 798, 608 - wl_y, fill='url(#waterGrad)'))
    el.append(_line(1070, wl_y, 1868, wl_y, stroke='#38bdf8', stroke_width='1.5', stroke_dasharray='8,4'))
    el.append(_text(1080, wl_y - 6, 'Calm Waterline (Draft T=0.56m)', font_family='Consolas, monospace', font_size='10.2', fill='#7dd3fc'))

    # Main hull side profile
    hull_side = [
        (3.65, 0.62), (3.10, 0.85), (2.25, 0.96), (-1.90, 0.94), (-2.38, 0.88),
        (-2.38, 0.24), (-1.60, 0.08), (0.80, 0.00), (2.20, 0.06), (3.10, 0.28),
    ]
    el.append(_poly([pt_side(x, z) for x, z in hull_side], fill='url(#hullGrad)', stroke='#94a3b8', stroke_width='1.8'))
    # Canopy dome
    can_side = [(2.30, 0.94), (1.70, 1.38), (0.75, 1.60), (-0.25, 1.48), (-0.95, 0.96)]
    el.append(_poly([pt_side(x, z) for x, z in can_side], fill='#0ea5e9', fill_opacity='0.28', stroke='#7dd3fc', stroke_width='1.3'))

    # Tail pylon + fin + Rudder [4] + T-Tail Elevator [3]
    fin_side = [(-1.60, 0.92), (-2.12, 0.96), (-3.06, 2.28), (-2.55, 2.34), (-1.85, 1.40)]
    el.append(_poly([pt_side(x, z) for x, z in fin_side], fill='#243245', stroke='#94a3b8', stroke_width='1.5'))
    rud_side = [(-2.16, 0.96), (-3.10, 2.20), (-3.50, 2.20), (-2.62, 0.96)]
    el.append(_poly([pt_side(x, z) for x, z in rud_side], fill='#0284c7', fill_opacity='0.70', stroke=C_CYAN, stroke_width='1.8'))
    # Horizontal tail + Elevator [3]
    el.append(_poly([pt_side(-2.72, 2.34), pt_side(-3.14, 2.34), pt_side(-3.14, 2.24), pt_side(-2.72, 2.24)],
                    fill='#334155', stroke='#94a3b8', stroke_width='1.2'))
    el.append(_poly([pt_side(-3.14, 2.34), pt_side(-3.56, 2.33), pt_side(-3.56, 2.25), pt_side(-3.14, 2.24)],
                    fill=C_CYAN, stroke='#e0f2fe', stroke_width='1.5'))

    # Ducted fan + Thrust line + Reverse bucket [5/6]
    fx0, fz0 = pt_side(F[0] - 0.30, F[2] + 0.46)
    fx1, fz1 = pt_side(F[0] + 0.35, F[2] - 0.46)
    el.append(_rect(min(fx0, fx1), min(fz0, fz1), abs(fx1 - fx0), abs(fz1 - fz0),
                    rx='6', fill='#334155', stroke=C_GOLD, stroke_width='2'))
    # Thrust line
    tx0, tz0 = pt_side(F[0] + 0.35, F[2])
    tx1, tz1 = pt_side(F[0] + 2.40, F[2])
    el.append(_line(tx0, tz0, tx1, tz1, stroke=C_GOLD, stroke_width='1.8', stroke_dasharray='6,3', marker_end='url(#arrGold)'))
    el.append(_text(tx1 - 15, tz0 - 8, 'Thrust Line (z=1.56m, 0.87m above CG)',
                    text_anchor='middle', font_family='Consolas, monospace', font_size='10.2', fill=C_GOLD))
    # Reverse bucket deployed arc
    rb_p = pt_side(REV_P[0], REV_P[2])
    el.append(_poly([pt_side(-2.33, 2.02), pt_side(-2.68, 1.94), pt_side(-2.68, 1.24), pt_side(-2.33, 1.18)],
                    fill=C_RED, fill_opacity='0.42', stroke=C_RED, stroke_width='1.8'))

    # Sponson + Option 1 Main Ski [7/8] + Strut + Fin (solid orange)
    s1 = opt1['skis']
    sp_side = [(S[0] + 1.55, S[2] + 0.08), (S[0] - 1.25, S[2] + 0.12), (S[0] - 1.25, S[2] - 0.12), (S[0] + 1.20, S[2] - 0.12)]
    el.append(_poly([pt_side(x, z) for x, z in sp_side], fill='#1e293b', fill_opacity='0.65', stroke=C_PURPLE, stroke_width='1.4', stroke_dasharray='4,2'))
    p1x, p1z = S[0] + s1['pivot_in_sponson_m'][0], S[2] + s1['pivot_in_sponson_m'][2]
    # Strut
    el.append(_line(*pt_side(p1x - 0.25, S[2] - 0.10), *pt_side(p1x, p1z), stroke='#94a3b8', stroke_width='5'))
    # Ski blade (Opt 1)
    el.append(_poly([
        pt_side(p1x + (s1['length_m'] - s1['hinge_from_trailing_edge_m']), p1z - s1['bottom_below_pivot_m'] + 0.05),
        pt_side(p1x - s1['hinge_from_trailing_edge_m'], p1z - s1['bottom_below_pivot_m'] + 0.04),
        pt_side(p1x - s1['hinge_from_trailing_edge_m'], p1z - s1['bottom_below_pivot_m']),
        pt_side(p1x + (s1['length_m'] - s1['hinge_from_trailing_edge_m']), p1z - s1['bottom_below_pivot_m']),
    ], fill=C_ORANGE, stroke='#ffedd5', stroke_width='1.5'))
    # Tracking fin (Opt 1)
    fx_fin = p1x + s1['fin']['x_from_pivot_m']
    el.append(_poly([
        pt_side(fx_fin + 0.14, p1z - s1['bottom_below_pivot_m']),
        pt_side(fx_fin - 0.14, p1z - s1['bottom_below_pivot_m']),
        pt_side(fx_fin - 0.14, p1z - s1['bottom_below_pivot_m'] - s1['fin']['span_m']),
        pt_side(fx_fin + 0.08, p1z - s1['bottom_below_pivot_m'] - s1['fin']['span_m']),
    ], fill='#c2410c', stroke=C_ORANGE, stroke_width='1.3'))

    # Option 2 Hydrofoil-Ski dashed overlay on Side Elevation (derived directly from opt2 JSON)
    s2 = opt2['skis']
    p2x, p2z = S[0] + s2['pivot_in_sponson_m'][0], S[2] + s2['pivot_in_sponson_m'][2]
    s2_le = p2x + (s2['length_m'] - s2['hinge_from_trailing_edge_m'])
    s2_te = p2x - s2['hinge_from_trailing_edge_m']
    s2_bot = p2z - s2['bottom_below_pivot_m']
    s2_top = s2_bot + s2['thickness_m']
    el.append(_line(*pt_side(p2x - 0.25, S[2] - 0.10), *pt_side(p2x, p2z), stroke='#fde047', stroke_width='2', stroke_dasharray='4,3'))
    el.append(_poly([
        pt_side(s2_le, s2_top), pt_side(s2_te, s2_top - 0.01),
        pt_side(s2_te, s2_bot), pt_side(s2_le, s2_bot),
    ], fill='#fde047', fill_opacity='0.35', stroke='#fde047', stroke_width='1.6', stroke_dasharray='4,2'))

    # Aft Trim Ski [9] + strut + tracking fin (Opt 1 solid green, Opt 2 dashed lime, derived from JSON)
    a1 = opt1['aft_ski']
    ap1_x, ap1_z = a1['pivot_in_airframe_m'][0], a1['pivot_in_airframe_m'][2]
    a1_le = ap1_x + (a1['length_m'] - a1['hinge_from_trailing_edge_m'])
    a1_te = ap1_x - a1['hinge_from_trailing_edge_m']
    a1_bot = ap1_z - a1['bottom_below_pivot_m']
    a1_top = a1_bot + a1['thickness_m']
    el.append(_line(*pt_side(ap1_x, a1['strut']['anchor_z_airframe_m']), *pt_side(ap1_x, ap1_z), stroke='#94a3b8', stroke_width='4'))
    el.append(_poly([
        pt_side(a1_le, a1_top), pt_side(a1_te, a1_top),
        pt_side(a1_te, a1_bot), pt_side(a1_le, a1_bot),
    ], fill=C_GREEN, stroke='#dcfce7', stroke_width='1.4'))
    # Aft tracking fin (Opt 1)
    af_x = ap1_x + a1['fin']['x_from_pivot_m']
    el.append(_poly([
        pt_side(af_x + 0.5 * a1['fin']['chord_m'], a1_bot),
        pt_side(af_x - 0.5 * a1['fin']['chord_m'], a1_bot),
        pt_side(af_x - 0.5 * a1['fin']['chord_m'], a1_bot - a1['fin']['span_m']),
        pt_side(af_x + 0.3 * a1['fin']['chord_m'], a1_bot - a1['fin']['span_m']),
    ], fill='#15803d', stroke=C_GREEN, stroke_width='1.2'))

    a2 = opt2['aft_ski']
    ap2_x, ap2_z = a2['pivot_in_airframe_m'][0], a2['pivot_in_airframe_m'][2]
    a2_le = ap2_x + (a2['length_m'] - a2['hinge_from_trailing_edge_m'])
    a2_te = ap2_x - a2['hinge_from_trailing_edge_m']
    a2_bot = ap2_z - a2['bottom_below_pivot_m']
    a2_top = a2_bot + a2['thickness_m']
    el.append(_poly([
        pt_side(a2_le, a2_top), pt_side(a2_te, a2_top - 0.008),
        pt_side(a2_te, a2_bot), pt_side(a2_le, a2_bot),
    ], fill='#86efac', fill_opacity='0.35', stroke='#86efac', stroke_width='1.4', stroke_dasharray='4,2'))

    # CG on Side Elevation (measured 19-DOF MuJoCo CG: x=0.325 m, z=0.693 m)
    cgxs, cgzs = pt_side(0.325, 0.693)
    el.append(f'<circle cx="{cgxs:.1f}" cy="{cgzs:.1f}" r="6" fill="none" stroke="{C_GOLD}" stroke-width="2"/>')
    el.append(_text(cgxs + 10, cgzs - 5, 'CG', font_family='Consolas, monospace', font_size='10.5', font_weight='700', fill=C_GOLD))

    # Side Elevation Annotations (clean open-space placement, zero overlap with geometry)
    el.append(_callout(*pt_side(-3.35, 2.30), 1300, 212, '3', 'Elevator [-20..+20 deg]', 'Pitch + WIG Attitude', C_CYAN, align='start', elbow_x=1240))
    el.append(_callout(*pt_side(-2.55, 1.68), 1345, 268, '5', 'Reverse Buckets [0..85 deg]', 'Jet Deflector Braking Flare', C_RED, align='start', elbow_x=1305))
    el.append(_callout(*pt_side(-2.85, 1.48), 1345, 322, '4', 'Rudder Cove Cleared [-30..+30 deg]', '0 Fin Interference at Full Travel', C_CYAN, align='start', elbow_x=1305))
    el.append(_callout(*pt_side(p1x + 0.1, p1z - 0.12), 1608, 570, '7', 'Main Skis Ahead of CG', 'Opt1 Planing / Opt2 Foil', C_ORANGE, align='start', elbow_x=1590))
    el.append(_callout(*pt_side(ap1_x - 0.1, ap1_z - 0.08), 1105, 570, '9', 'Aft Trim Ski/Foil', 'Stern Pitch Stabilizer', C_GREEN, align='start', elbow_x=1100))

    # 19-DOF Summary Pill Bar at bottom of Sub-Panel A2
    el.append(_rect(1074, 622, 790, 54, rx='7', fill='#0d1520', stroke=C_BORDER, stroke_width='1.2'))
    pills = [
        (1084, 134, '#334155', '6 FREE HULL', 'X Y Z Roll Pitch Yaw'),
        (1224, 140, '#581c87', '2 SPONSON FLEX', '+/-0.06m Z Slide'),
        (1370, 140, '#854d0e', '2 EMRAX FANS', 'Port + Stbd Spin'),
        (1516, 338, '#075985', '9 ACTIVE CONTROL SURFACES', '2 Ail · 1 Elev · 1 Rud · 2 Buckets · 2 Main Skis · 1 Aft Ski'),
    ]
    for px, pw, pbg, pt1, pt2 in pills:
        el.append(_rect(px, 630, pw, 38, rx='5', fill=pbg, stroke='#475569', stroke_width='1'))
        el.append(_text(px + pw / 2, 646, pt1, text_anchor='middle', font_family='Segoe UI, Arial, sans-serif', font_size='10.4', font_weight='800', fill='#f8fafc'))
        el.append(_text(px + pw / 2, 661, pt2, text_anchor='middle', font_family='Consolas, monospace', font_size='8.9', fill='#cbd5e1'))

    # =========================================================================
    # PANEL B: CLOSED-LOOP ARCHITECTURE (HUMAN HELM + TELEMETRY-ONLY AI -> ECU -> PLANT)
    # =========================================================================
    el.append(_rect(24, 722, 1140, 594, rx='12', fill=C_PANEL, stroke=C_BORDER, stroke_width='1.5'))
    el.append(_text(44, 750, 'B. DUAL-AUTHORITY CLOSED-LOOP CONTROL: HUMAN HELM UI & TELEMETRY-ONLY AI PILOT',
                    font_family='Segoe UI, Arial, sans-serif', font_size='14.5', font_weight='800', fill=C_GOLD, letter_spacing='0.4'))

    # Box 1A: Human Pilot
    el.append(_rect(44, 770, 316, 178, rx='9', fill=C_SUB, stroke=C_GOLD, stroke_width='1.8'))
    el.append(_rect(44, 770, 316, 28, rx='9', fill='#422006'))
    el.append(_text(58, 789, 'HUMAN PILOT  (public/vtx-env/harbour.js)', font_family='Segoe UI, Arial, sans-serif', font_size='11.5', font_weight='800', fill=C_GOLD))
    human_lines = [
        '• Profile Selector: RC01-P1-R1 / RC01-H1-R1 / CA-1 / CA-0',
        '• Primary Helm: Throttle, Rudder, Reverse Bucket, Cut',
        '• Surface Trim: Diff Thrust, Elevator, Ailerons',
        '• Hydro-Skis & ECU: Collective, Diff, Aft Ski, ECU Assist',
        '• Live Readout: ECU mode, achieved deg, load %, [SAT]',
        '• Cockpit / Chase / Top 3D views (body_poses stream)',
    ]
    for i, ln in enumerate(human_lines):
        el.append(_text(56, 818 + i * 20, ln, font_family='Segoe UI, Arial, sans-serif', font_size='10.8', fill=C_TEXT))

    # Box 1B: Telemetry-Only AI Pilot
    el.append(_rect(44, 968, 316, 240, rx='9', fill=C_SUB, stroke=C_CYAN, stroke_width='1.8'))
    el.append(_rect(44, 968, 316, 28, rx='9', fill='#082f49'))
    el.append(_text(58, 987, 'AI PILOT — TELEMETRY ONLY  (Colin / Agent)', font_family='Segoe UI, Arial, sans-serif', font_size='11.5', font_weight='800', fill=C_CYAN))
    ai_lines = [
        'STRICT CONTRACT: NO map cheating, NO truth forces',
        '1. READ  GET /api/observe  (sensor_observation):',
        '   · gnss_xy_m, baro_m, water_clearance_m, draft_m',
        '   · attitude_xyz_deg, heading_deg, gyro_world_deg_s',
        '   · body_velocity_mps, airspeed_m_s, fan_rpm',
        '   · control_surfaces (cmd/ach deg, Nm, load %, SAT)',
        '   · ski_telemetry (regime, d_te/d_le, hinge Nm)',
        '   · ecu_status (mode, target_roll/pitch) & lamps',
        '2. WRITE POST /api/action  (schema: ricochet-1):',
        '   · 10 bounded channels (hold_until_changed + clamp)',
    ]
    for i, ln in enumerate(ai_lines):
        col = C_RED if i == 0 else (C_CYAN if ln.startswith(('1.', '2.')) else C_TEXT)
        fw = '700' if i in (0, 1, 8) else '400'
        el.append(_text(55, 1015 + i * 19, ln, font_family='Consolas, Segoe UI, monospace', font_size='9.6', font_weight=fw, fill=col))

    # Box 2: Action Normalizer & 5-Mode ECU
    el.append(_rect(418, 770, 352, 438, rx='9', fill=C_SUB, stroke=C_GREEN, stroke_width='1.8'))
    el.append(_rect(418, 770, 352, 28, rx='9', fill='#052e16'))
    el.append(_text(432, 789, 'ACTION CONTRACT + ON-BOARD 5-MODE ECU', font_family='Segoe UI, Arial, sans-serif', font_size='11.5', font_weight='800', fill=C_GREEN))

    # Sub-box inside Box 2: RicochetAction validator
    el.append(_rect(432, 810, 324, 62, rx='6', fill='#0f172a', stroke='#334155', stroke_width='1'))
    el.append(_text(442, 828, 'normalize_ricochet_action() -> RicochetAction', font_family='Consolas, monospace', font_size='10.8', font_weight='700', fill='#a7f3d0'))
    el.append(_text(442, 845, '10 channels · hold_until_changed · fail-safe clamp', font_family='Consolas, monospace', font_size='9.8', fill=C_MUTED))
    el.append(_text(442, 861, 'Supports numeric, deg/rad/%, & text clauses', font_family='Consolas, monospace', font_size='9.8', fill=C_MUTED))

    # 5 ECU Modes stack
    el.append(_text(432, 894, '5-MODE SPEED-SCHEDULED ECU (ecu_assist in [0..1]):', font_family='Segoe UI, Arial, sans-serif', font_size='10.8', font_weight='800', fill=C_GREEN))
    ecu_modes = [
        ('1. displacement', 'u < 3.0 m/s', 'Low-speed diff thrust + rudder + bucket pivot', '#1e293b', '#94a3b8'),
        ('2. hump_transition', '3.0 - 11.5 m/s', 'High ski coll. + elev hump bias -> hull clear', '#431407', C_ORANGE),
        ('3. on_plane_foil', '11.5 - 23.0 m/s', 'Ski washout + height hold + inward bank +/-12°', '#082f49', C_CYAN),
        ('4. wig_skim', 'u >= 23.0 m/s', 'Aero pitch/roll/heave stab across wing handoff', '#2e1065', C_PURPLE),
        ('5. braking_flare', 'rev > 0.08 / cut', 'Anti-dive flare (+2° ski, +4° elev, -1° aft)', '#450a0a', C_RED),
    ]
    for i, (mname, mcond, mdesc, mbg, mcol) in enumerate(ecu_modes):
        my = 904 + i * 48
        el.append(_rect(432, my, 324, 41, rx='5', fill=mbg, stroke=mcol, stroke_width='1.1'))
        el.append(_text(442, my + 16, mname, font_family='Consolas, monospace', font_size='10.8', font_weight='700', fill=mcol))
        el.append(_text(746, my + 16, mcond, text_anchor='end', font_family='Consolas, monospace', font_size='9.8', fill='#e2e8f0'))
        el.append(_text(442, my + 33, mdesc, font_family='Segoe UI, Arial, sans-serif', font_size='10.2', fill='#cbd5e1'))

    el.append(_text(432, 1160, 'Pilot Trim Override: pilot_cmd + ecu_assist * ecu_cmd', font_family='Consolas, monospace', font_size='9.5', fill='#86efac'))
    el.append(_text(432, 1178, 'Turn Bank Target: clip(turn_norm * 10°, +/-12°)', font_family='Consolas, monospace', font_size='9.5', fill=C_MUTED))
    el.append(_text(432, 1196, 'Bank Lift Comp: +1.5*(1/cos(phi)-1)° to skis & elev', font_family='Consolas, monospace', font_size='9.5', fill=C_MUTED))

    # Box 3: 400 Hz MuJoCo 19-DOF Plant + Real Actuators + Water
    el.append(_rect(828, 770, 318, 438, rx='9', fill=C_SUB, stroke=C_ORANGE, stroke_width='1.8'))
    el.append(_rect(828, 770, 318, 28, rx='9', fill='#431407'))
    el.append(_text(842, 789, '400 Hz MUJOCO 19-DOF PLANT & WATER', font_family='Segoe UI, Arial, sans-serif', font_size='11.5', font_weight='800', fill=C_ORANGE))

    plant_sections = [
        ('REAL OFF-THE-SHELF ACTUATORS:', C_GOLD, [
            '• 3x Volz DA 30-HT-D (2 Ail, Elev): 36/64 Nm, 165°/s',
            '• 4x Volz DA 58-D (Rud, 2 Buckets, Aft): 80/200 Nm',
            '• 2x Exlar GSX30 (Main Skis, 0.44m): 1,416 Nm, 33°/s',
            '• 2x EMRAX 228 MV (Ducted Fans): 200 Nm, 68 kW',
        ]),
        ('HYDRO & AERO PHYSICS:', C_CYAN, [
            '• Reflective SWE Basin (0.0m rest err) + Kelvin Wake',
            '• Opt 1 (RC01-P1-R1): Savitsky 3-Pt Planing Skis',
            '• Opt 2 (RC01-H1-R1): NACA 4412 Hydrofoil Skis',
            '• Raymer Mesh Aero Drag (CdA 0.545-0.550 m^2)',
            '• Rudder-Linked Fins (steer_link 0.20 / 0.25-0.30)',
        ]),
        ('SAFETY & QUALIFICATION (PASS 4/4):', C_GREEN, [
            '• Load-dependent slew & [SAT] saturation lamps',
            '• Explicit CAPSIZED & IMPACT outcome latches',
            '• Opt 1: Clear 8.0s · 21.1 m/s · S-Turn & Brake PASS',
            '• Opt 2: Clear 3.7s · 23.4 m/s · S-Turn & Brake PASS',
        ]),
    ]
    py_cur = 816
    for hdr, hcol, items in plant_sections:
        el.append(_text(840, py_cur, hdr, font_family='Segoe UI, Arial, sans-serif', font_size='10.8', font_weight='800', fill=hcol))
        py_cur += 18
        for it in items:
            el.append(_text(840, py_cur, it, font_family='Segoe UI, Arial, sans-serif', font_size='10.2', fill=C_TEXT))
            py_cur += 19
        py_cur += 12

    # Signal-flow arrows inside Panel B
    # Human -> Action/ECU
    el.append(_line(360, 845, 414, 845, stroke=C_GOLD, stroke_width='2.4', marker_end='url(#arrGold)'))
    el.append(_text(387, 835, 'UI Cmd', text_anchor='middle', font_family='Consolas, monospace', font_size='9.5', fill=C_GOLD))
    # AI -> Action/ECU
    el.append(_line(360, 1050, 414, 1050, stroke=C_CYAN, stroke_width='2.4', marker_end='url(#arrCyan)'))
    el.append(_text(387, 1040, '/action', text_anchor='middle', font_family='Consolas, monospace', font_size='9.5', fill=C_CYAN))
    # ECU -> MuJoCo Plant
    el.append(_line(770, 980, 824, 980, stroke=C_GREEN, stroke_width='2.6', marker_end='url(#arrGreen)'))
    el.append(_text(797, 968, '11 Act.', text_anchor='middle', font_family='Consolas, monospace', font_size='9.5', fill=C_GREEN))

    # Closed Telemetry Feedback Loop along bottom of Panel B
    el.append(
        f'<path d="M987,1208 L987,1282 L202,1282 L202,1212" fill="none" stroke="{C_CYAN}" '
        f'stroke-width="2.4" marker-end="url(#arrCyan)"/>'
    )
    el.append(_rect(430, 1266, 494, 32, rx='6', fill='#082f49', stroke=C_CYAN, stroke_width='1.2'))
    el.append(_text(677, 1286, 'TELEMETRY-ONLY FEEDBACK LOOP  (GET /api/observe  +  3D body_poses)',
                    text_anchor='middle', font_family='Consolas, monospace', font_size='11', font_weight='700', fill='#e0f2fe'))
    # Branch to Human UI telemetry
    el.append(
        f'<path d="M202,1282 L34,1282 L34,885 L42,885" fill="none" stroke="{C_GOLD}" '
        f'stroke-width="1.6" stroke-dasharray="5,3" marker-end="url(#arrGold)"/>'
    )

    # =========================================================================
    # PANEL C: MANEUVERABILITY MATRIX & 10-CHANNEL SIGN REFERENCE
    # =========================================================================
    el.append(_rect(1182, 722, 714, 594, rx='12', fill=C_PANEL, stroke=C_BORDER, stroke_width='1.5'))
    el.append(_text(1202, 750, 'C. MANEUVERABILITY ALLOCATION & 10-CHANNEL SIGN GUIDE',
                    font_family='Segoe UI, Arial, sans-serif', font_size='14.5', font_weight='800', fill=C_GOLD, letter_spacing='0.4'))

    # Table 1: 5 Core Maneuvers
    el.append(_rect(1200, 766, 678, 24, rx='4', fill='#1e293b'))
    el.append(_text(1210, 782, 'MANEUVER / REGIME', font_family='Segoe UI, Arial, sans-serif', font_size='10.5', font_weight='800', fill=C_GOLD))
    el.append(_text(1365, 782, 'ACTIVE SURFACES & COMMANDS', font_family='Segoe UI, Arial, sans-serif', font_size='10.5', font_weight='800', fill=C_CYAN))
    el.append(_text(1652, 782, 'AI TELEMETRY WATCHPOINTS', font_family='Segoe UI, Arial, sans-serif', font_size='10.5', font_weight='800', fill=C_GREEN))

    maneuvers = [
        ('Docking / Pivot', '< 3 m/s (Displ.)', 'Diff Thrust + Rudder [4] + Buckets [5,6]', 'Low throttle + reverse pulse', 'gnss_xy_m, heading_deg', 'water_clearance_m > 0.2m'),
        ('Hump Takeoff', '3 - 12 m/s', 'Throttle 1.0 + Main Skis [7,8] + Elev [3]', 'Aft Ski [9] damps bow rise', 'draft_m -> 0, pitch +2..4°', 'ski hinge < 1,416 Nm'),
        ('Coordinated Turn', '12 - 23 m/s', 'Rudder [4] + Ski Diff [7,8] + Ailerons [1,2]', 'Fins steer-linked; inward bank', 'roll < 18°, yaw_rate smooth', 'zero SERVO_SATURATED'),
        ('WIG Skim Cruise', '>= 23 m/s', 'Elev [3] + Ail [1,2] + Rud [4] + Skis [7-9]', 'Skis wash out to -2.5..+1.5°', 'baro_m, airspeed_m_s', 'pitch/roll rate damping'),
        ('Braking Flare', 'Stop / Abort', 'Reverse Buckets [5,6]=1.0 + Throttle 0.3->0', 'ECU flare: +2°ski +4°el -1°aft', 'nose_up > -6° (no dive)', 'CAPSIZED=False, u -> 0'),
    ]
    for i, (m1, m2, s1_t, s2_t, t1_t, t2_t) in enumerate(maneuvers):
        ry = 794 + i * 47
        bg = '#151e2b' if i % 2 == 0 else '#111824'
        el.append(_rect(1200, ry, 678, 44, rx='4', fill=bg, stroke='#1f2c3d', stroke_width='1'))
        el.append(_text(1210, ry + 18, m1, font_family='Segoe UI, Arial, sans-serif', font_size='11', font_weight='700', fill='#f8fafc'))
        el.append(_text(1210, ry + 34, m2, font_family='Consolas, monospace', font_size='9.5', fill=C_MUTED))
        el.append(_text(1365, ry + 18, s1_t, font_family='Segoe UI, Arial, sans-serif', font_size='10.0', font_weight='600', fill='#e2e8f0'))
        el.append(_text(1365, ry + 34, s2_t, font_family='Segoe UI, Arial, sans-serif', font_size='9.6', fill=C_MUTED))
        el.append(_text(1652, ry + 18, t1_t, font_family='Consolas, monospace', font_size='9.6', fill='#86efac'))
        el.append(_text(1652, ry + 34, t2_t, font_family='Consolas, monospace', font_size='9.5', fill='#94a3b8'))

    # Table 2: Exact 10-Channel /api/action Reference
    el.append(_text(1202, 1054, 'EXACT 10-CHANNEL /api/action SCHEMA (ricochet-1) & SIGN CONVENTIONS:',
                    font_family='Segoe UI, Arial, sans-serif', font_size='11.5', font_weight='800', fill=C_CYAN))

    channels = [
        ('throttle', '[0, 1]', 'Twin EMRAX 228 forward thrust', C_GOLD),
        ('differential_thrust', '[-1, +1]', '+ Stbd > Port -> Nose-Left Yaw', C_GOLD),
        ('rudder_deg', '[-30, +30]°', '+ TE Port -> Nose-Left Yaw', C_CYAN),
        ('elevator_deg', '[-20, +20]°', '+ TE Up -> Nose-Up Pitch', C_CYAN),
        ('aileron_deg', '[-25, +25]°', '+ Stbd TE Up / Port Down -> Right Roll', C_CYAN),
        ('reverse_bucket', '[0, 1]', '0..85° Jet Deflector -> Water Brake', C_RED),
        ('ski_incidence_deg', '[-2..10 / -4..10]°', '+ Leading Edge Up -> Lift / Heave', C_ORANGE),
        ('ski_differential_deg', '[-4, +4]°', '+ Port LE Up / Stbd Down -> Right Roll', C_ORANGE),
        ('aft_ski_incidence_deg', '[-3..8 / -6..8]°', '+ Stern Lift -> Nose-Down Trim', C_GREEN),
        ('ecu_assist', '[0, 1]', '0 = Pure Manual · 1 = Full 5-Mode ECU', C_PURPLE),
    ]
    for idx, (ch, rng, desc, col) in enumerate(channels):
        col_i = idx // 5
        row_i = idx % 5
        bx = 1200 + col_i * 343
        by = 1066 + row_i * 46
        el.append(_rect(bx, by, 335, 40, rx='5', fill=C_SUB, stroke='#273549', stroke_width='1'))
        el.append(_rect(bx, by, 4.5, 40, rx='2', fill=col))
        el.append(_text(bx + 12, by + 16, ch, font_family='Consolas, monospace', font_size='10.5', font_weight='700', fill='#f8fafc'))
        el.append(_text(bx + 326, by + 16, rng, text_anchor='end', font_family='Consolas, monospace', font_size='9.8', fill=col))
        el.append(_text(bx + 12, by + 32, desc, font_family='Segoe UI, Arial, sans-serif', font_size='9.8', fill=C_MUTED))

    # Footer
    el.append(_text(
        W / 2, H - 8,
        'Authoritative Single Source: concept_a_builder.py · inputs/ricochet_profiles/rc01_{planing_3pt,hydrofoil_ski}_v1.json · real_components.py · live.py · harbour.js',
        text_anchor='middle', font_family='Consolas, monospace', font_size='10', fill='#64748b',
    ))
    el.append('</svg>\n')
    return '\n'.join(el)


def _find_headless_browser() -> str | None:
    candidates = [
        shutil.which('msedge'),
        shutil.which('chrome'),
        shutil.which('chromium'),
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/usr/bin/chromium',
        '/usr/bin/google-chrome',
    ]
    for cand in candidates:
        if cand and pathlib.Path(cand).is_file():
            return cand
    return None


def _render_png(svg_path: pathlib.Path, png_path: pathlib.Path, width: int = 1920, height: int = 1340) -> bool:
    browser = _find_headless_browser()
    if not browser:
        return False
    with tempfile.TemporaryDirectory(prefix='rc01_diag_') as tmpdir:
        html_path = pathlib.Path(tmpdir) / 'diagram.html'
        html_path.write_text(
            '<!doctype html><html><head><meta charset="utf-8">'
            '<style>html,body{margin:0;padding:0;background:#0b1017;overflow:hidden;width:1920px;height:1340px;}'
            'img{display:block;width:1920px;height:1340px;}</style></head>'
            f'<body><img src="{svg_path.as_uri()}"></body></html>',
            encoding='utf-8',
        )
        cmd = [
            browser,
            '--headless=new',
            '--disable-gpu',
            '--hide-scrollbars',
            f'--window-size={width},{height}',
            '--force-device-scale-factor=1',
            f'--screenshot={png_path}',
            html_path.as_uri(),
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0 and png_path.is_file()


def main() -> None:
    out_dir = pathlib.Path(__file__).resolve().parent
    out_svg = out_dir / 'ricochet_control_surfaces_diagram.svg'
    out_png = out_dir / 'ricochet_control_surfaces_diagram.png'
    svg = build_svg()
    out_svg.write_text(svg, encoding='utf-8')
    print(f'Wrote {out_svg} ({len(svg):,} bytes)')
    if _render_png(out_svg, out_png):
        print(f'Wrote {out_png} ({out_png.stat().st_size:,} bytes)')
    else:
        print('Note: headless Edge/Chrome not found; skipped PNG rasterization (SVG updated).')


if __name__ == '__main__':
    main()
