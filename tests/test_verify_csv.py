# Copyright (c) 2026 Chile Ingenieria SPA. All rights reserved.
"""Synthetic numerical controls; never claim they exercised the private engine."""
import csv
import math
import tempfile
import unittest
from pathlib import Path

from verify_csv import AuditError, COLUMNS, audit_csv


def fixture(path, *, defect=None):
    dt, g, rho = 0.0001, 9.81, 7850.0
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for step in (0, 1, 10, 50):
            for pid, diameter in enumerate((0.13970, 0.15875)):
                radius = diameter / 2
                mass = 4 * math.pi * radius**3 * rho / 3
                z0 = 2.0 + pid * .5
                z = z0 - g * dt**2 * step * (step + 1) / 2
                if defect == "wrong_integrator" and step == 50 and pid == 0:
                    z += 0.002
                item = {name: 0 for name in COLUMNS}
                item.update(step=step, time_s=step * dt, id=pid,
                            z_m=z, vz_m_s=-g * dt * step,
                            radius_m=radius, mass_kg=mass,
                            fz_N=-mass * g, inertia_kg_m2=0.4 * mass * radius**2)
                if defect == "nonfinite" and step == 10 and pid == 0:
                    item["vz_m_s"] = float("nan")
                if defect == "bad_radius" and step == 10 and pid == 0:
                    item["radius_m"] = -1
                w.writerow(item)
                if defect == "duplicate" and step == 10 and pid == 0:
                    w.writerow(item)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "synthetic.csv"

    def run_case(self, defect=None, **args):
        fixture(self.path, defect=defect)
        return audit_csv(self.path, **args)

    def test_synthetic_freefall_two_sag_diameters(self):
        result = self.run_case(freefall_dt=0.0001)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["particle_count"], 2)
        self.assertEqual(result["frames"], 4)
        self.assertFalse(result["industrial_validation"])
        self.assertEqual(len(result["source_sha256"]), 64)

    def test_structure_only_does_not_claim_physics(self):
        result = self.run_case(defect="wrong_integrator")
        self.assertEqual(result["scope"], "fixed_inventory_csv_structure_only")

    def test_wrong_integrator_rejected(self):
        with self.assertRaisesRegex(AuditError, "Free-fall"):
            self.run_case("wrong_integrator", freefall_dt=0.0001)

    def test_nonfinite_rejected(self):
        with self.assertRaises(AuditError):
            self.run_case("nonfinite")

    def test_duplicate_particle_rejected(self):
        with self.assertRaises(AuditError):
            self.run_case("duplicate")

    def test_bad_radius_rejected(self):
        with self.assertRaises(AuditError):
            self.run_case("bad_radius")

    def test_wrong_dt_rejected(self):
        with self.assertRaises(AuditError):
            self.run_case(freefall_dt=0.0002)

    def test_empty_file_rejected(self):
        self.path.write_text("", encoding="utf-8")
        with self.assertRaises(AuditError):
            audit_csv(self.path)

    def test_stable_digest_for_identical_input(self):
        a = self.run_case()
        b = audit_csv(self.path)
        self.assertEqual(a["source_sha256"], b["source_sha256"])


if __name__ == "__main__":
    unittest.main()
