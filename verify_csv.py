# Copyright (c) 2026 Chile Ingenieria SPA. All rights reserved.
"""Independent, read-only contract/oracle checker for DEM particle CSV outputs.

This file is original test infrastructure. It does NOT contain DEM Studio's solver.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

COLUMNS = (
    "step,time_s,id,x_m,y_m,z_m,vx_m_s,vy_m_s,vz_m_s,"
    "fx_N,fy_N,fz_N,radius_m,mass_kg,wx_rad_s,wy_rad_s,wz_rad_s,"
    "tx_N_m,ty_N_m,tz_N_m,inertia_kg_m2"
).split(",")
FLOAT_COLUMNS = [name for name in COLUMNS if name not in ("step", "id")]
MAX_ROWS = 500_000


class AuditError(ValueError):
    pass


def audit_csv(path, *, freefall_dt=None, gravity=9.81):
    """Check schema, fixed-inventory consistency, and optional free-fall oracle.

    The oracle is only valid for contact-free semi-implicit Euler with constant g.
    PASS here never means industrial, STL, friction, or GPU validation.
    """
    path = Path(path)
    if freefall_dt is not None and (not math.isfinite(freefall_dt) or freefall_dt <= 0):
        raise AuditError("Invalid positive time step")
    if not math.isfinite(gravity) or gravity <= 0:
        raise AuditError("Invalid gravity")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)

    first = {}
    previous_step = None
    previous_time = None
    seen = set()
    frames = 0
    rows = 0
    expected_ids = None
    with path.open("r", newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != COLUMNS:
            raise AuditError("CSV schema differs from the known 21-column contract")
        for item in reader:
            rows += 1
            if rows > MAX_ROWS:
                raise AuditError("Input exceeds fixed audit row limit")
            try:
                step = int(item["step"])
                pid = int(item["id"])
                values = {key: float(item[key]) for key in FLOAT_COLUMNS}
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                raise AuditError(f"Malformed numeric field at data row {rows}") from exc
            if step < 0 or pid < 0 or not all(map(math.isfinite, values.values())):
                raise AuditError(f"Nonfinite/negative index at row {rows}")
            if any(values[key] <= 0 for key in ("radius_m", "mass_kg", "inertia_kg_m2")):
                raise AuditError(f"Invalid particle properties at row {rows}")
            t = values["time_s"]
            if t < 0:
                raise AuditError(f"Negative simulation time at row {rows}")
            if step != previous_step:
                if previous_step is not None:
                    if step <= previous_step or t <= previous_time:
                        raise AuditError("Steps/times must strictly increase between frames")
                    if seen != expected_ids:
                        raise AuditError("Missing particle in preceding fixed-inventory frame")
                else:
                    expected_ids = set()
                frames += 1
                seen = set()
                previous_step, previous_time = step, t
            elif not math.isclose(t, previous_time, rel_tol=0, abs_tol=1e-12):
                raise AuditError("Inconsistent times within frame")
            if pid in seen:
                raise AuditError("Duplicate particle ID in a frame")
            seen.add(pid)
            if frames == 1:
                if pid in first:
                    raise AuditError("Duplicate ID in initial frame")
                first[pid] = (step, t, values["z_m"], values["vz_m_s"],
                              values["radius_m"], values["mass_kg"])
                expected_ids.add(pid)
            else:
                if pid not in first:
                    raise AuditError("Unexpected particle in fixed-inventory case")
                origin_step, origin_time, z0, vz0, r0, m0 = first[pid]
                if values["radius_m"] != r0 or values["mass_kg"] != m0:
                    raise AuditError("Particle radius/mass changed between frames")
                if freefall_dt is not None:
                    n = step - origin_step
                    expected_t = origin_time + n * freefall_dt
                    expected_vz = vz0 - gravity * n * freefall_dt
                    expected_z = z0 + vz0 * n * freefall_dt - (
                        gravity * freefall_dt ** 2 * n * (n + 1) / 2
                    )
                    if (abs(t - expected_t) > 5e-9 or
                        abs(values["vz_m_s"] - expected_vz) > 5e-8 or
                        abs(values["z_m"] - expected_z) > 5e-8):
                        raise AuditError(f"Free-fall oracle failed at step={step}, id={pid}")
        if frames < 2 or not first:
            raise AuditError("Require initial and final frames with particles")
        if seen != expected_ids:
            raise AuditError("Missing particle in last fixed-inventory frame")
    return {
        "status": "PASS",
        "scope": "fixed_inventory_csv_and_semi_implicit_freefall" if freefall_dt is not None
                 else "fixed_inventory_csv_structure_only",
        "frames": frames, "particle_count": len(first), "rows": rows,
        "source_sha256": digest.hexdigest(),
        "industrial_validation": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", help="CSV produced by an independently executed solver")
    parser.add_argument("--freefall-dt", type=float, default=None)
    parser.add_argument("--gravity", type=float, default=9.81)
    args = parser.parse_args()
    try:
        result = audit_csv(args.csv, freefall_dt=args.freefall_dt, gravity=args.gravity)
    except (AuditError, OSError, UnicodeError, csv.Error) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
