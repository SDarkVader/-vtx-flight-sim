"""Quasi-steady per-surface aerodynamics for the Phantom (Phase 2 low-speed subset).

Each surface: local air velocity at its aerodynamic centre from v_body + w x r - wind_body;
alpha in the surface (chord, normal) plane; attached CL = CLa (alpha - alpha0) blended by a
sigmoid into a flat-plate model (CN = flat_plate_cn sin alpha) beyond stall, valid at all angles
and inverted. Force at the AC (body frame). Exactly zero at zero relative airspeed. Wing lift is
scaled by the deployed fraction and is zero when stowed; flap and aileron increments act only
when the wing is locked. Folded canards produce no force. Hinge moments from Ch_alpha/Ch_delta.
Geometry comes from the handover JSON of the selected wing-cassette revision (A9 or A10).
"""
from __future__ import annotations
import math
import numpy as np


def _sig(a, a0, M):
    e1 = math.exp(min(50, -M * (a - a0))); e2 = math.exp(min(50, M * (a + a0)))
    return (1 + e1 + e2) / ((1 + e1) * (1 + e2))


def coefficients(alpha, cla, alpha0, alpha_stall, cd0, k_ind, cn_fp, M):
    s = _sig(alpha, alpha_stall, M)
    cl_att = cla * (alpha - alpha0)
    cd_att = cd0 + k_ind * cl_att * cl_att
    cl_fp = cn_fp * math.sin(alpha) * math.cos(alpha)
    cd_fp = cd0 + cn_fp * math.sin(alpha) ** 2
    return (1 - s) * cl_att + s * cl_fp, (1 - s) * cd_att + s * cd_fp, s


class Surface:
    def __init__(self, name, ac, chord_dir, normal, area, cla, alpha0, alpha_stall, cd0, k_ind, kind, side=None, ch=(0.0, 0.0), chord=0.3):
        self.name = name; self.ac = np.array(ac, float); self.c = np.array(chord_dir, float) / np.linalg.norm(chord_dir)
        self.n = np.array(normal, float) / np.linalg.norm(normal); self.area = area; self.cla = cla; self.alpha0 = alpha0
        self.alpha_stall = alpha_stall; self.cd0 = cd0; self.k_ind = k_ind; self.kind = kind; self.side = side; self.ch = ch; self.chord = chord


class SurfaceAero:
    def __init__(self, P):
        self.P = P; H = P.handover['aero_surfaces']; A = P.tree['aero']
        self.rho = P['atmosphere.density_kg_m3']
        w = H['wing']; self.wing = w
        basis = P['aero.wing_basis']
        S_side = w['S_ref_m2'] / 2 if basis == 'screening' else w['S_exposed_each_m2']
        AR = w['span_m'] ** 2 / w['S_ref_m2']; k = 1 / (math.pi * AR * P['aero.wing_oswald_e'])
        a_st = w['CLmax_clean'] / w['CLalpha_per_rad_M0']
        self.cn_fp = P['aero.flat_plate_cn']; self.M = P['aero.stall_blend_rate']
        self.surfaces = []
        inc = math.radians(P['proposals.p8_wing_incidence_deg'])      # P8: geometric incidence (chord and normal rotated, LE up)
        cw, nw = [math.cos(inc), 0.0, math.sin(inc)], [-math.sin(inc), 0.0, math.cos(inc)]
        for side, s, z in (('left', 1, w['ac_height_R_m']), ('right', -1, w['ac_height_L_m'])):
            self.surfaces.append(Surface(f'wing_{side}', [w['x_ac_mac_m'], s * w['y_mac_m'], z], cw, nw, S_side, w['CLalpha_per_rad_M0'],
                                         -w['cm0'] * 0.0 - math.radians(2.0), a_st, P['aero.wing_cd0'], k, 'wing', side, chord=w['mac_m']))
        ail = H['aileron']; flp = H['flap']
        y_ail = (np.mean(ail['eta'])); y_flp = np.mean(flp['eta'])
        root = 1.245; span_exp = w['span_m'] / 2 - root
        self.strips = {}
        for side, s, z in (('left', 1, w['ac_height_R_m']), ('right', -1, w['ac_height_L_m'])):
            self.strips[f'aileron_{side}'] = dict(pos=np.array([w['x_ac_mac_m'] - 0.25, s * (root + y_ail * span_exp), z]), area=P['aero.aileron_strip_area_m2'],
                                                  tau=ail['tau'], ch=(ail['Ch_alpha'], ail['Ch_delta']), cs_area=ail['area_each_m2'], cs_chord=0.12)
            self.strips[f'flap_{side}'] = dict(pos=np.array([w['x_ac_mac_m'] - 0.25, s * (root + y_flp * span_exp), z]), area=P['aero.flap_strip_area_m2'],
                                               tau=flp['tau'], ch=(ail['Ch_alpha'], ail['Ch_delta']), cs_area=flp['area_each_m2'], cs_chord=0.18)
        cn = H['canard']; scale = P['proposals.p5_canard_area_scale']
        yc = (cn['y_root_m'] + cn['y_tip_m']) / 2
        for side, s in (('left', 1), ('right', -1)):
            self.surfaces.append(Surface(f'canard_{side}', [cn['x_pivot_m'], s * yc, cn['z_m']], [1, 0, 0], [0, 0, 1], cn['area_each_m2'] * scale, cn['CLalpha_per_rad'], 0.0,
                                         math.radians(P['aero.canard_stall_deg']), P['aero.canard_cd0'], 0.1, 'canard', side, (P['aero.canard_hinge_ch_alpha'], 0.0)))
        if P['proposals.p6_drs_stabilator'] > 0.5:
            # P6: split DRS flap between the fins flown as an all-moving stabilator (engineering/phantom/drs_flap.py).
            # Inverted cambered section: CL = CLa (alpha - alpha0) with alpha0 > 0 (downforce at zero incidence).
            # The trailing-edge-up deflection (state['stab_te_up'], rad) reduces the local angle of attack.
            # eta_q scales the dynamic pressure through the area.
            self.surfaces.append(Surface('drs_stab', P['proposals.p6_stab_position_m'], [1, 0, 0], [0, 0, 1],
                                         P['proposals.p6_stab_area_m2'] * P['proposals.p6_stab_eta_q'], P['proposals.p6_stab_cla_per_rad'],
                                         math.radians(P['proposals.p6_stab_alpha0_deg']), math.radians(12.0), 0.012, 0.052, 'stab', None,
                                         (0.0, 0.0), 0.24))
        fp = np.array(P['aero.fin_position_m']); cant = math.radians(P['aero.fin_cant_deg'])
        for side, s in (('left', 1), ('right', -1)):
            self.surfaces.append(Surface(f'fin_{side}', fp * [1, s, 1], [1, 0, 0], [0, s * math.cos(cant), -math.sin(cant)], P['aero.fin_area_each_m2'],
                                         P['aero.fin_cl_alpha'], 0.0, math.radians(15), 0.012, 0.15, 'fin', side))
        g = P.geometry['projected_areas']
        self.body_cda = np.array([g['frontal_m2'] * P['aero.body_cd_frontal'], g['side_m2'] * P['aero.body_cd_side'], g['plan_m2'] * P['aero.body_cd_plan']])
        self.body_centre = np.array(P['aero.body_centre_m'])

    def compute(self, v_body, w_body, wind_body, state):
        """state: wing_frac{left,right}, wing_locked{..}, flap{..} aileron{..} rad, canard_pitch{..} rad, canard_deployed{..}.
        Returns dict(force, moment about body origin, per-surface list, hinge moments)."""
        F = np.zeros(3); Mo = np.zeros(3); out = []; hinge = {}
        def air(r):
            return v_body + np.cross(w_body, r) - wind_body
        for s in self.surfaces:
            frac = 1.0; extra_inc = 0.0
            if s.kind == 'wing':
                frac = state['wing_frac'][s.side]
            elif s.kind == 'canard':
                if not state['canard_deployed'][s.side]:
                    frac = 0.0
                extra_inc = state['canard_pitch'][s.side]
            elif s.kind == 'stab':
                extra_inc = -state.get('stab_te_up', 0.0)
            if frac <= 0:
                out.append(dict(name=s.name, alpha_deg=0.0, q_pa=0.0, cl=0.0, cd=0.0, force_n=[0, 0, 0], active=False)); continue
            v = air(s.ac)
            span = np.cross(s.c, s.n)
            vp = v - (v @ span) * span
            V = float(np.linalg.norm(vp))
            if V < 1e-6:
                out.append(dict(name=s.name, alpha_deg=0.0, q_pa=0.0, cl=0.0, cd=0.0, force_n=[0, 0, 0], active=True)); continue
            alpha = math.atan2(-(vp @ s.n), vp @ s.c) + extra_inc
            cl, cd, stall = coefficients(alpha, s.cla, s.alpha0, s.alpha_stall, s.cd0, s.k_ind, self.cn_fp, self.M)
            q = 0.5 * self.rho * V * V
            ddir = -vp / V; ldir = np.cross(ddir, span); ldir /= np.linalg.norm(ldir)
            f = q * s.area * frac * (cl * ldir + cd * ddir)
            F += f; Mo += np.cross(s.ac, f)
            if s.kind == 'canard':
                hinge[s.name] = q * s.area * s.chord * s.ch[0] * alpha
            out.append(dict(name=s.name, alpha_deg=math.degrees(alpha), q_pa=q, cl=cl, cd=cd, stall_blend=stall, force_n=f.tolist(), active=True))
            if s.kind == 'wing':
                for cs in ('flap', 'aileron'):
                    st = self.strips[f'{cs}_{s.side}']
                    d = state[cs][s.side]
                    if not state['wing_locked'][s.side]:
                        out.append(dict(name=f'{cs}_{s.side}', locked=False, force_n=[0, 0, 0])); continue
                    va = air(st['pos']); vpa = va - (va @ span) * span; Va = float(np.linalg.norm(vpa))
                    if Va < 1e-6:
                        continue
                    qa = 0.5 * self.rho * Va * Va
                    dcl = s.cla * st['tau'] * d * (1 - stall)
                    dcd = self.P['aero.flap_delta_cd_per_rad'] * abs(d)
                    dd = -vpa / Va; ld = np.cross(dd, span); ld /= np.linalg.norm(ld)
                    fs = qa * st['area'] * frac * (dcl * ld + dcd * dd)
                    F += fs; Mo += np.cross(st['pos'], fs)
                    hinge[f'{cs}_{s.side}'] = qa * st['cs_area'] * st['cs_chord'] * (st['ch'][0] * alpha + st['ch'][1] * d)
                    out.append(dict(name=f'{cs}_{s.side}', locked=True, delta_deg=math.degrees(d), dcl=dcl, force_n=fs.tolist()))
        vb = air(self.body_centre)
        fb = -0.5 * self.rho * np.abs(vb) * vb * self.body_cda
        F += fb; Mo += np.cross(self.body_centre, fb)
        out.append(dict(name='body', force_n=fb.tolist(), cda_m2=self.body_cda.tolist(), munk_moment='not modelled'))
        return dict(force_body=F, moment_body=Mo, surfaces=out, hinge_moments=hinge)
