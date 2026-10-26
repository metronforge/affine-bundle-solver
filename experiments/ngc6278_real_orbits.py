#!/usr/bin/env python3
"""Real-galaxy orbital-weight case, using the upstream DYNAMITE NNLS matrix.

This is NOT an ABS NNLS implementation: ABS solves unconstrained dense Ax=b,
while scipy.optimize.nnls enforces non-negative orbit weights. This experiment
quantifies the distinction on a matrix assembled from CALIFA observations of
NGC 6278 and orbits integrated by DYNAMITE.

Sources:
https://github.com/dynamics-of-stellar-systems/dynamite
https://dynamics.univie.ac.at/dynamite_docs/tutorial_notebooks/2_quickstart.html
"""
from __future__ import annotations

import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import platform
import sys

import numpy as np
from scipy import __version__ as scipy_version, optimize


ROOT = Path(__file__).resolve().parents[1]
DYNAMITE_DIR = ROOT / "external" / "dynamite"
WORKDIR = DYNAMITE_DIR / "docs" / "tutorial_notebooks"
RESULT_DIR = ROOT / "results" / "real-ngc6278"


class Policy(C.Structure):
    _fields_ = [
        ("struct_size", C.c_size_t),
        ("dependence_threshold", C.c_double),
        ("growth_threshold", C.c_double),
        ("compatibility_tolerance", C.c_double),
        ("quality_threshold", C.c_double),
    ]


class SolveResult(C.Structure):
    _fields_ = [
        ("struct_size", C.c_size_t),
        ("policy_used", Policy),
        ("operational_status", C.c_int),
        ("operational_certainty", C.c_int),
        ("exact_source_status", C.c_int),
        ("exact_source_verification", C.c_int),
        ("router_meta", C.c_double * 11),
        ("grey_distinct_count", C.c_int),
        ("grey_total_events", C.c_int),
        ("grey_rows", C.c_int * 64),
        ("last_orth_eta", C.c_double),
        ("core_rank_interval", C.c_int * 2),
        ("core_qr_rank", C.c_int),
        ("formation_guard_counters", C.c_ulonglong * 3),
    ]


class CandidateCheck(C.Structure):
    _fields_ = [
        ("struct_size", C.c_size_t),
        ("policy_used", Policy),
        ("verdict", C.c_int),
        ("max_abs_residual_up", C.c_double),
        ("mixed_backward_error_up", C.c_double),
    ]


PTR = C.POINTER(C.c_double)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class NativeABS:
    def __init__(self) -> None:
        self.lib = C.CDLL(str(ROOT / "libcertified_solver.so"))
        self.lib.bs_default_operational_policy.argtypes = [C.POINTER(Policy)]
        self.lib.bs_init_solve_result.argtypes = [C.POINTER(SolveResult)]
        self.lib.bs_init_candidate_check_result.argtypes = [C.POINTER(CandidateCheck)]
        self.lib.bsolve.argtypes = [
            PTR, PTR, C.c_int, C.c_int,
            C.POINTER(Policy), PTR, C.POINTER(SolveResult),
        ]
        self.lib.bsolve.restype = C.c_int
        self.lib.abs_check_candidate.argtypes = [
            PTR, PTR, PTR, C.c_int, C.c_int,
            C.POINTER(Policy), C.POINTER(CandidateCheck),
        ]
        self.lib.abs_check_candidate.restype = C.c_int

    def run(self, A: np.ndarray, b: np.ndarray) -> dict:
        A = np.ascontiguousarray(A, dtype=np.float64)
        b = np.ascontiguousarray(b, dtype=np.float64)
        assert A.ndim == 2 and b.shape == (A.shape[0],)
        assert np.all(np.isfinite(A)) and np.all(np.isfinite(b))
        m, n = A.shape
        assert m > 0 and n > 0
        policy, result, quality = Policy(), SolveResult(), CandidateCheck()
        x = np.zeros(n, dtype=np.float64)
        self.lib.bs_default_operational_policy(C.byref(policy))
        self.lib.bs_init_solve_result(C.byref(result))
        rc = self.lib.bsolve(
            A.ctypes.data_as(PTR), b.ctypes.data_as(PTR), m, n,
            C.byref(policy), x.ctypes.data_as(PTR), C.byref(result),
        )
        if rc:
            raise RuntimeError(f"bsolve returned {rc} for matrix {A.shape}")
        self.lib.bs_init_candidate_check_result(C.byref(quality))
        qc = self.lib.abs_check_candidate(
            A.ctypes.data_as(PTR), b.ctypes.data_as(PTR),
            x.ctypes.data_as(PTR), m, n, C.byref(policy), C.byref(quality),
        )
        if qc:
            raise RuntimeError(f"abs_check_candidate returned {qc}")
        return {
            "solver": "native ABS bsolve + abs_check_candidate",
            "bsolve_return_code": int(rc),
            "operational_status_code": int(result.operational_status),
            "operational_certainty_code": int(result.operational_certainty),
            "rank_estimate": int(result.router_meta[2]),
            "rank_interval": [int(result.router_meta[3]), int(result.router_meta[4])],
            "exact_source_status_code": int(result.exact_source_status),
            "max_abs_residual": float(np.max(np.abs(A @ x - b))),
            "l2_residual": float(np.linalg.norm(A @ x - b)),
            "negative_weight_count": int(np.count_nonzero(x < -1e-10)),
            "min_weight": float(x.min()),
            "candidate_verdict_code": int(quality.verdict),
            "candidate_mixed_backward_error_up": float(quality.mixed_backward_error_up),
            "solution": x,
        }


def prepare_galaxy() -> tuple[np.ndarray, np.ndarray, int, dict]:
    if not (WORKDIR / "NGC6278_config_single.yaml").exists():
        raise FileNotFoundError("Pinned DYNAMITE checkout is missing")
    os.chdir(WORKDIR)
    import dynamite as dyn
    from dynamite.data_prep.generate_kin_input import create_kin_input

    in_file = WORKDIR / "NGC6278_input" / "NGC6278.V1200.rscube_INDOUSv2_SN20_stellar_kin.fits"
    out_dir = WORKDIR / "NGC6278_input" / "dynamite_input"
    if not in_file.is_file():
        raise FileNotFoundError(f"Real CALIFA FITS input unavailable: {in_file}")
    out_dir.mkdir(parents=True, exist_ok=True)
    create_kin_input("NGC6278", str(in_file), str(out_dir) + "/",
                     expr="", fit_PA=True, kin_input="CALIFA")
    gh = dyn.kinematics.GaussHermite()
    gh.add_psf_to_datafile(sigma=[1.06], weight=[1.0],
                           datafile=str(out_dir / "gauss_hermite_kins.ecsv"))

    cfg = dyn.config_reader.Configuration(
        "NGC6278_config_single.yaml",
        reset_logging=True, reset_existing_output=True)
    dyn.model_iterator.ModelIterator(cfg)
    model = cfg.all_models.get_model_from_row(0)
    orblib = model.get_orblib()
    orblib.read_vel_histograms()
    weight_solver = dyn.weight_solvers.NNLS(config=cfg, model=model)
    A, b = weight_solver.construct_nnls_matrix_and_rhs(orblib)
    A = np.ascontiguousarray(A, dtype=np.float64)
    b = np.ascontiguousarray(b, dtype=np.float64)
    assert A.shape[0] == b.size and A.shape[1] == orblib.n_orbs
    assert np.all(np.isfinite(A)) and np.all(np.isfinite(b))
    provenance = {
        "galaxy": "NGC 6278",
        "input": "DYNAMITE CALIFA FITS, reduced by DYNAMITE",
        "raw_fits_sha256": digest(in_file),
        "config_sha256": digest(WORKDIR / "NGC6278_config_single.yaml"),
        "dynamite_version": dyn.__version__,
        "kinematic_bins": int(len(cfg.system.get_unique_triaxial_visible_component().kinematic_data[0].data)),
        "matrix_rows": int(A.shape[0]),
        "matrix_columns": int(A.shape[1]),
        "mass_constraint_rows": int(weight_solver.n_mass_constraints),
        "scipy_version": scipy_version,
        "python_version": platform.python_version(),
    }
    return A, b, int(weight_solver.n_mass_constraints), provenance


def experiment_case(name: str, A: np.ndarray, b: np.ndarray,
                    abs_solver: NativeABS) -> dict:
    w_nnls, _ = optimize.nnls(A, b, maxiter=6 * A.shape[1])
    assert np.all(np.isfinite(w_nnls))
    assert w_nnls.min() >= -1e-12
    result = abs_solver.run(A, b)
    result["name"] = name
    result["shape"] = list(A.shape)
    result["nonnegative_reference"] = {
        "solver": "scipy.optimize.nnls",
        "l2_residual": float(np.linalg.norm(A @ w_nnls - b)),
        "active_orbits": int(np.count_nonzero(w_nnls > 1e-9)),
        "min_weight": float(w_nnls.min()),
    }
    print(json.dumps({k: v for k, v in result.items() if k != "solution"},
                     sort_keys=True, allow_nan=True), flush=True)
    return result


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    A, b, n_mass, provenance = prepare_galaxy()
    np.savez_compressed(RESULT_DIR / "NGC6278_real_orbit_matrix.npz",
                        A=A, b=b, n_mass=n_mass)
    abs_solver = NativeABS()
    cases = [
        experiment_case("mass_constraints", A[:n_mass], b[:n_mass], abs_solver),
        experiment_case("kinematic_constraints", A[n_mass:], b[n_mass:], abs_solver),
        experiment_case("combined_observations", A, b, abs_solver),
    ]
    for case in cases:
        case.pop("solution")
    report = {
        "provenance": provenance,
        "cases": cases,
        "interpretation": (
            "Native ABS solves unconstrained dense least-squares/equalities; "
            "SciPy NNLS solves nonnegative weights. This is a methodological "
            "comparison, not evidence that ABS implements NNLS or recovers "
            "a unique phase-space distribution."
        ),
    }
    (RESULT_DIR / "results.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=True) + "\n")
    print("CASE_COMPLETE", RESULT_DIR / "results.json", flush=True)


if __name__ == "__main__":
    main()
