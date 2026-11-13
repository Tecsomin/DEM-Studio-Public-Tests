# DEM Studio — independent public checks (minimum export)

Copyright (c) 2026 Chile Ingenieria SPA. All rights reserved.

This directory is deliberately independent of the DEM Studio proprietary C++
solver. Its purpose is to make a small, reproducible numerical and CSV-output
verification harness eligible for standard GitHub Actions on a **separate**
public repository with **fresh Git history**.

## What the free public CI actually tests
- CSV structural integrity of fixed-inventory synthetic DEM trajectories;
- two nominal SAG ball diameters (139.70 and 158.75 mm);
- the semi-implicit Euler constant-gravity closed-form reference;
- explicit negative controls (duplicate particle, NaN, altered radius, wrong
  integrator, wrong time step, missing data);
- Python harness on Linux and Windows; no third-party dependencies.

Run: `python -m unittest discover -s tests -v`.

When a permitted, independently compiled private binary produces a sanitized
CSV, the same public verifier can be run separately:
`python verify_csv.py permitted_output.csv`.
Add `--freefall-dt 0.0001` **only** if it is a true contact-free constant-gravity
semi-implicit Euler case. Do not publish industrial trajectories.

## Crucial limitations
A PASS of this repository **does not execute or validate the private DEM Studio
engine**. It does not prove STL contact, friction, conveyor belts, 20k/50k/100k
scaling, native Windows GUI, GPU performance or industrial SAG V&V.
Private source compilation/execution still requires private CI or an approved
isolated runner. Never pass private source or credentials to public PR workflows.

The public export must contain exactly the checked-in files on an explicit
allowlist. It must never include Git history, compiled engines, industrial STL,
customer data, benchmark raw files or internal CI logs.

## Legal status
See NOTICE.md. Source for the DEM Studio engine and external dependencies is
not included. No open-source license to the proprietary engine is granted.
