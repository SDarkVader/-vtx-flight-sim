import numpy as np

def radius_of_curvature(p0, p1, p2, p3, t):
    d1 = 3*(1-t)**2 * (p1 - p0) + 6*(1-t)*t * (p2 - p1) + 3*t**2 * (p3 - p2)
    d2 = 6*(1-t) * (p2 - 2*p1 + p0) + 6*t * (p3 - 2*p2 + p1)
    speed = np.linalg.norm(d1)
    if speed < 1e-6: return float('inf')
    cross = abs(d1[0]*d2[1] - d1[1]*d2[0])
    if cross < 1e-6: return float('inf')
    return (speed ** 3) / cross

# Test smoother entry curve
# P0 = [-625, 0], heading +Y -> P1 = [-625, 45]
# P3 = [-650, 100], heading -X or entering TWY-A at [-650, 100]
# If tangent at P3 is parallel to TWY-A (heading -X or +X):
# TWY-A runs from -650 to +650 along Y=100.
# So at Y=100, tangent should be along (+1, 0) or (-1, 0).
# Since it merges into TWY-A at -650 pointing EAST (+1, 0):
# P2 = [-650 - 40, 100] would be coming from west.
# But it comes from runway at X=-625 (which is EAST of -650!).
# Coming from -625 to -650 means moving WEST!
# If it merges into TWY-A heading EAST (+X), it would turn through 90 deg clockwise?
# Runway is at Y=0. TWY-A is at Y=100.
# Aircraft exits Runway 08 (heading East) by turning LEFT (North) at X=-625,
# then turning RIGHT (East) to join TWY-A heading East!
# So at P0=[-625, 0], initial tangent is along exit angle (e.g. 45 deg or 90 deg).
# If 90 deg: tangent is +Y.
# At P3, it joins TWY-A heading EAST (+X).
# So P3=[-600, 100] or P3=[-625+R, 100] with tangent (+1, 0)!
# Let's see: if P0=[-625, 0], P1=[-625, 55], P2=[-630, 100], P3=[-650, 100]:
for factor in [0.3, 0.4, 0.5, 0.55]:
    # Smooth S-curve / transition fillet
    # Let's test standard fillet where P0 = [-625, 0], P3 = [-650, 100]
    p0 = np.array([-625., 0.])
    p1 = np.array([-625., 100 * factor])
    p2 = np.array([-650. + 25 * factor, 100.])
    p3 = np.array([-650., 100.])
    ts = np.linspace(0.01, 0.99, 100)
    rs = [radius_of_curvature(p0, p1, p2, p3, t) for t in ts]
    print(f"factor {factor}: min R = {min(rs):.1f}m at t={ts[np.argmin(rs)]:.2f}")

# What if P0=[-625, 0], P1=[-625, 45], P2=[-660, 80], P3=[-650, 100]?
p0 = np.array([-625., 0.])
p1 = np.array([-625., 45.])
p2 = np.array([-655., 75.])
p3 = np.array([-650., 100.])
ts = np.linspace(0.01, 0.99, 100)
rs = [radius_of_curvature(p0, p1, p2, p3, t) for t in ts]
print(f"custom 1: min R = {min(rs):.1f}m")

# Or what if P0=[-625, 0], P1=[-625, 45], P2=[-675, 85], P3=[-650, 100]?
p0 = np.array([-625., 0.])
p1 = np.array([-625., 45.])
p2 = np.array([-670., 90.])
p3 = np.array([-650., 100.])
rs = [radius_of_curvature(p0, p1, p2, p3, t) for t in ts]
print(f"custom 2: min R = {min(rs):.1f}m")
