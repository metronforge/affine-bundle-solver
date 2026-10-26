#!/usr/bin/env python3
"""Real FCC 167 (NGC 1380) Schwarzschild orbit-weight comparison.

Uses preprocessed published Fornax3D observations from pinned upstream DYNAMITE
without synthetic substitution. Uses real native Affine-Bundle Solver on the
DYNAMITE-built orbit-weight matrix and compares to SciPy NNLS.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform

import numpy as np
from scipy import __version__ as scipy_version

from ngc6278_real_orbits import NativeABS, experiment_case, digest, ROOT, WORKDIR


OUT = ROOT / "results" / "real-fcc167"


def assemble():
    os.chdir(WORKDIR)
    import dynamite as dyn

    config_file = WORKDIR / "FCC167_config.yaml"
    data_dir = WORKDIR / "FCC167_input"
    required = [
        config_file,
        data_dir / "mge.ecsv",
        data_dir / "gauss_hermite_kins.ecsv",
        data_dir / "aperture.dat",
        data_dir / "bins.dat",
        data_dir / "met_es.ecsv",
        data_dir / "aperture_pops.dat",
        data_dir / "bins_pops.dat",
    ]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f"Published FCC167 input missing: {path}")
    cfg = dyn.config_reader.Configuration(
        config_file.name, reset_logging=True, reset_existing_output=True)
    dyn.model_iterator.ModelIterator(config=cfg, plots=False)
    model = cfg.all_models.get_model_from_row(0)
    orblib = model.get_orblib()
    orblib.read_vel_histograms()
    nnls = dyn.weight_solvers.NNLS(config=cfg, model=model)
    A, b = nnls.construct_nnls_matrix_and_rhs(orblib)
    A = np.ascontiguousarray(A, dtype=np.float64)
    b = np.ascontiguousarray(b, dtype=np.float64)
    if not (A.shape[1] == orblib.n_orbs and A.shape[0] == b.size):
        raise RuntimeError(f"Unexpected orbit shape {A.shape}, rhs {b.shape}")
    if not np.all(np.isfinite(A)) or not np.all(np.isfinite(b)):
        raise RuntimeError("Nonfinite observational orbit matrix")
    provenance = {
        "galaxy": "FCC 167 / NGC 1380",
        "source": "DYNAMITE Fornax3D prepared observations and integrated orbits",
        "input_sha256": {
            str(p.relative_to(WORKDIR)): digest(p) for p in required
        },
        "python_version": platform.python_version(),
        "scipy_version": scipy_version,
        "dynamite_version": dyn.__version__,
        "matrix_rows": int(A.shape[0]),
        "matrix_columns": int(A.shape[1]),
        "mass_constraint_rows": int(nnls.n_mass_constraints),
    }
    return A, b, int(nnls.n_mass_constraints), provenance


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    A, b, k, provenance = assemble()
    np.savez_compressed(OUT / "FCC167_real_orbit_matrix.npz", A=A, b=b, n_mass=k)
    native = NativeABS()
    cases = [
        experiment_case("mass_constraints", A[:k], b[:k], native),
        experiment_case("kinematic_constraints", A[k:], b[k:], native),
        experiment_case("combined_observations", A, b, native),
    ]
    for result in cases:
        result.pop("solution")
    (OUT / "results.json").write_text(
        json.dumps({"provenance": provenance, "cases": cases}, indent=2,
                   sort_keys=True, allow_nan=True) + "\n")
    print("FCC167_CASE_COMPLETE", OUT / "results.json", flush=True)


if __name__ == "__main__":
    main()
