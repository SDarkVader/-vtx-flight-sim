import sys
sys.path.insert(0, 'src')
from vtx.world import TestWorld

w = TestWorld()
for x in [-625, -450, -245, -180, 0, 100, 235, 585, 625]:
    for y in [0, 50, 100, 200, 300]:
        h = w.terrain_z(x, y)
        if h > 0.1:
            print(f"Elevation at ({x:4d}, {y:3d}) = {h:.2f}m")
