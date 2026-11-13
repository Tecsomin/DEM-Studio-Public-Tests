# Private-engine to public-verifier transfer contract

Copyright (c) 2026 Chile Ingenieria SPA. All rights reserved.

## Architecture
1. Build and execute DEM Studio exclusively in a controlled private environment. No private C++ sources, binary, tokens, industrial STL, customer trajectory or Git history may enter public CI.
2. Export a **synthetic, contact-free** trajectory with declared integrator, gravity, time step, particle inventory and nominal radii; sanitize all metadata before transfer.
3. Run the existing public `verify_csv.py` against that exported CSV. For semi-implicit Euler constant-gravity cases, use `--freefall-dt` only when its analytical assumptions are satisfied.
4. Store private performance results (20k/50k/100k particles; hardware, threads, compiler flags, seed, wall-time per step, peak RSS, x/v/omega checksums) in the private repository. Publish only approved aggregated metrics.
5. Keep LIGGGHTS comparisons deferred until an explicit final acceptance gate requires them.

## Acceptance gates
- Public CI passes its independent unit tests on Linux and Windows.
- A **real private solver output** passes the same independent CSV verifier, with provenance and hash retained privately.
- Separate independent analytical contact, friction, rotation, dynamic STL and energy/momentum tests pass before any industrial claims.
- 20k/50k/100k runs report repeatable timing, memory and numerical drift; compare A/B with matched conditions.
- Windows binary, GUI, and representative SAG chute-to-belt-to-chute physics remain **unverified** until separately executed.

## Security release checklist
- Explicit allowlist of exported files and fields; deny all other artifacts.
- No raw industrial geometry, customer data, proprietary implementation, compiled solver, credentials, CI logs or full particle trajectories in public artifacts.
- Review every export for sensitive paths, identifiers, embedded metadata and accidentally committed secrets.
- Never use a public PR runner to checkout the private engine or access its secrets.

This protocol alone does not validate the private solver or unblock its execution environment.
