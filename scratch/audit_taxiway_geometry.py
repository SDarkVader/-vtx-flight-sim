import json
import numpy as np

def cubic_bezier(p0, p1, p2, p3, t):
    return (1-t)**3 * p0 + 3*(1-t)**2*t * p1 + 3*(1-t)*t**2 * p2 + t**3 * p3

def bezier_tangent(p0, p1, p2, p3, t):
    return 3*(1-t)**2 * (p1 - p0) + 6*(1-t)*t * (p2 - p1) + 3*t**2 * (p3 - p2)

def bezier_second_deriv(p0, p1, p2, p3, t):
    return 6*(1-t) * (p2 - 2*p1 + p0) + 6*t * (p3 - 2*p2 + p1)

def radius_of_curvature(p0, p1, p2, p3, t):
    d1 = bezier_tangent(p0, p1, p2, p3, t)
    d2 = bezier_second_deriv(p0, p1, p2, p3, t)
    speed = np.linalg.norm(d1)
    if speed < 1e-6:
        return float('inf')
    cross = abs(d1[0]*d2[1] - d1[1]*d2[0])
    if cross < 1e-6:
        return float('inf')
    return (speed ** 3) / cross

def run_audit():
    data = json.load(open('scratch/data_pack/VTX_fictional_airport_layout_proposal.json'))
    taxiways = data['taxiways']
    print("=== TAXIWAY GEOMETRY & CURVATURE AUDIT ===")
    
    aircraft_duct_radius = 3.805 # half-width of aircraft envelope (7.61m)
    gear_radius = 1.90 # half-width of gear contact footprint (3.80m)
    
    for twy in taxiways:
        twy_id = twy['id']
        kind = twy.get('kind', 'polyline')
        width = twy.get('width_m', 14)
        print(f"\nTaxiway {twy_id} (kind: {kind}, width: {width}m):")
        
        if kind == 'polyline':
            pts = np.array(twy['points_xy'])
            length = np.linalg.norm(pts[1] - pts[0])
            print(f"  Straight segment length: {length:.1f}m from {pts[0]} to {pts[1]}")
            print(f"  Curvature radius: Infinite (straight)")
            print(f"  Gear edge clearance: {(width/2 - gear_radius):.2f}m")
            print(f"  Duct edge clearance: {(width/2 - aircraft_duct_radius):.2f}m")
        elif kind == 'cubic_bezier':
            cps = np.array(twy['control_points_xy'])
            ts = np.linspace(0.01, 0.99, 100)
            radii = [radius_of_curvature(cps[0], cps[1], cps[2], cps[3], t) for t in ts]
            min_r = min(radii)
            min_t = ts[np.argmin(radii)]
            
            # Arc length approximation
            curve_pts = [cubic_bezier(cps[0], cps[1], cps[2], cps[3], t) for t in np.linspace(0, 1, 100)]
            arc_len = sum(np.linalg.norm(curve_pts[i+1] - curve_pts[i]) for i in range(len(curve_pts)-1))
            
            print(f"  Arc length: {arc_len:.1f}m")
            print(f"  Min radius of curvature: {min_r:.1f}m at t={min_t:.2f}")
            print(f"  ICAO Aerodrome Design Manual minimum recommended: 25.0m")
            print(f"  Curvature compliance: {'PASS (>=25m)' if min_r >= 25.0 else 'CHECK'}")
            print(f"  Undercarriage gear track (3.8m) edge clearance: {(width/2 - gear_radius):.2f}m")
            print(f"  Outer rotor duct (7.6m) edge clearance: {(width/2 - aircraft_duct_radius):.2f}m")

if __name__ == '__main__':
    run_audit()
