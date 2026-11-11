"""Stdlib safety regression for isolated Ricochet import contract."""
import csv
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'physics'))
from vtx_runtime_contract import (
    ReferenceLake, UnsupportedPhysics, axial_body_f03_to_vtx,
    polar_body_f03_to_vtx, inertia_tensor_f03_to_vtx,
    world_lake_reference, assert_physical_water_supported,
    f03_world_heading_deg, f03_velocity_body_projection, f03_to_world_position,
)

class TestImportContract(unittest.TestCase):
    def setUp(self):
        self.lake = world_lake_reference({'water': {'x': -265., 'y':30.,'half_x':28.,'half_y':80.}})

    def test_world_geometry_and_depth_provisional(self):
        self.assertTrue(self.lake.contains(-265, 30))
        self.assertTrue(self.lake.contains(-265, 80))
        self.assertFalse(self.lake.contains(-265, 112))
        self.assertEqual(self.lake.assumed_bed_z_m, -3.)

    def test_existing_water_fails_closed(self):
        with self.assertRaises(UnsupportedPhysics):
            assert_physical_water_supported({'water': {'x': -265., 'y': 30.}})
        with self.assertRaises(UnsupportedPhysics):
            assert_physical_water_supported({'water_physics_revision':'arbitrary', 'bathymetry_verified':True})

    def test_reflected_polar_and_axial_invariant(self):
        self.assertEqual(polar_body_f03_to_vtx((1, 2, 3)), (1., -2., 3.))
        self.assertEqual(axial_body_f03_to_vtx((1, 2, 3)), (-1., 2., -3.))
        # The cross product of two reflected POLAR vectors must be reflected AXIALLY.
        a, b = (1., 2., 3.), (4., 5., 6.)
        cross = (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
        aa, bb = polar_body_f03_to_vtx(a), polar_body_f03_to_vtx(b)
        cross_vtx = (aa[1]*bb[2]-aa[2]*bb[1], aa[2]*bb[0]-aa[0]*bb[2], aa[0]*bb[1]-aa[1]*bb[0])
        self.assertEqual(cross_vtx, axial_body_f03_to_vtx(cross))

    def test_inertia_reflection(self):
        I = [[2., .3, .4],[.3, 3., .5],[.4, .5, 4.]]
        II = inertia_tensor_f03_to_vtx(I)
        self.assertEqual(II, [[2., -.3, .4],[-.3, 3., -.5],[.4, -.5, 4.]])

    def test_corrected_heading(self):
        rec = dict(x_m=0., y_m=30., z_origin_m=-.37, yaw_deg=0., vx_mps=0., vy_mps=2.85)
        self.assertEqual(f03_world_heading_deg(rec), 90.)
        fwd, side = f03_velocity_body_projection(rec)
        self.assertAlmostEqual(fwd, 2.85)
        self.assertAlmostEqual(side, 0.,places=8)
        self.assertEqual(f03_to_world_position(rec,self.lake), (-265.,60.,-.37))

    def test_real_timeseries_heading_at_15s(self):
        csv_path = ROOT / 'data' / 'RC01_F03_nominal_timeseries.csv'
        if not csv_path.exists():self.skipTest('recorded telemetry missing')
        with csv_path.open(newline='') as fh:
            closest = min(csv.DictReader(fh),key=lambda r:abs(float(r['time_s'])-15.))
        fwd,side=f03_velocity_body_projection(closest)
        self.assertGreater(fwd,2.8)
        self.assertLess(abs(side),0.015)

if __name__ == '__main__':unittest.main()
