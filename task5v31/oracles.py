"""Independent standard and contract oracles with disjoint timing phases."""

import time
import numpy as np
from scipy.linalg import lstsq, qr

DEPENDENCE, GROWTH, QUALITY, COMPATIBILITY = 1e-13, 1e-9, 1e-14, 2e-10


def standard_oracle(a, b, slot):
    started = time.perf_counter_ns(); full = slot["standard_oracle_mode"] == "FULL"
    t = time.perf_counter_ns(); singular = np.linalg.svd(a, compute_uv=False) if full else None
    svd_ns = time.perf_counter_ns() - t
    t = time.perf_counter_ns(); _, r, _ = qr(a, pivoting=True, mode="economic")
    qr_ns = time.perf_counter_ns() - t; diagonal = np.abs(np.diag(r))
    scale = float(singular[0]) if singular is not None and len(singular) else float(diagonal[0]) if len(diagonal) else 0.0
    eps = np.finfo(float).eps; tau_abs = max(a.shape) * eps * scale
    cond_rel = max(a.shape) * eps if scale else 0.0
    rank_qr = int(np.count_nonzero(diagonal > tau_abs))
    rank_svd = int(np.count_nonzero(singular > tau_abs)) if singular is not None else None
    rank = rank_svd if rank_svd is not None else rank_qr
    t = time.perf_counter_ns()
    x, _, lstsq_rank, _ = lstsq(a, b, cond=cond_rel, lapack_driver="gelsd" if full else "gelsy")
    lstsq_ns = time.perf_counter_ns() - t
    residual = float(np.linalg.norm(a @ x - b))
    threshold = float(100 * eps * (scale * np.linalg.norm(x) + np.linalg.norm(b) + 1))
    status = "INCONSISTENT" if residual > threshold else "UNIQUE" if rank == a.shape[1] else "INFINITE"
    result = {"oracle_type": "FULL_SVD_QR" if full else "PIVOTED_QR",
              "method": "FULL_SVD_PLUS_PIVOTED_QR" if full else "PIVOTED_QR_STRUCTURAL_PLAN",
              "singular_values": singular.tolist() if singular is not None else None,
              "rank_svd": rank_svd, "rank_qr": rank_qr, "lstsq_rank": int(lstsq_rank),
              "numerical_rank_threshold": float(tau_abs), "least_squares_relative_cutoff": float(cond_rel),
              "compatibility_residual": residual, "compatibility_threshold": threshold,
              "standard_numerical_oracle_status": status,
              "svd_qr_rank_agree": None if rank_svd is None else rank_svd == rank_qr}
    total = time.perf_counter_ns() - started
    return result, {"standard_svd_ns": svd_ns, "standard_qr_ns": qr_ns, "standard_lstsq_ns": lstsq_ns,
                    "standard_other_ns": max(0, total - svd_ns - qr_ns - lstsq_ns)}


def contract_oracle(a, b):
    started = time.perf_counter_ns(); norms = np.linalg.norm(a, axis=1)
    an = np.zeros_like(a); bn = np.array(b, copy=True); nonzero = norms != 0
    an[nonzero] = a[nonzero] / norms[nonzero, None]; bn[nonzero] /= norms[nonzero]
    _, r, pivots = qr(an.T, pivoting=True, mode="economic"); diagonal = np.abs(np.diag(r))
    rank_lo, rank_hi = int(np.count_nonzero(diagonal > GROWTH)), int(np.count_nonzero(diagonal >= DEPENDENCE))
    grey = [{"position": int(i), "source_row": int(pivots[i]), "mu": float(diagonal[i])}
            for i in range(len(diagonal)) if DEPENDENCE <= diagonal[i] <= GROWTH]
    if rank_lo != rank_hi:
        status, bad, backward = "UNDECIDABLE", [], None
    else:
        x, *_ = lstsq(an, bn, lapack_driver="gelsy"); residual = a @ x - b; xnorm = float(np.linalg.norm(x))
        bad = np.flatnonzero(np.abs(residual) > COMPATIBILITY * (np.abs(b) + norms * (1 + xnorm))).astype(int).tolist()
        backward = float(np.max(np.abs(residual) / (np.abs(b) + norms * xnorm + 1e-300)))
        status = "INCONSISTENT" if bad else "UNIQUE" if rank_lo == a.shape[1] and backward <= QUALITY else "UNDECIDABLE" if rank_lo == a.shape[1] else "INFINITE"
    return {"solver_contract_oracle_status": status, "contract_rank_lo": rank_lo, "contract_rank_hi": rank_hi,
            "qrcp_grey_directions": grey, "qrcp_near_threshold": [float(x) for x in diagonal if x < 10 * GROWTH],
            "bad_compatibility_rows": bad, "rowwise_backward_error": backward,
            "published_dependence_threshold": DEPENDENCE, "published_growth_threshold": GROWTH,
            "published_quality_threshold": QUALITY}, time.perf_counter_ns() - started
