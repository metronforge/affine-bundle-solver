import numpy as np

from task5v31.campaign import generate_manifest
from task5v31.materialize import materialize
from task5v31.oracles import contract_oracle, standard_oracle


def test_standard_and_contract_oracles_keep_published_cutoffs():
    slots = generate_manifest()["slots"]
    for slot in slots:
        if not slot["eligibility"]["small"]:
            continue
        a, b, _ = materialize(slot)
        result, phases = standard_oracle(a, b, slot)
        contract, contract_ns = contract_oracle(a, b)
        scale = float(np.linalg.svd(a, compute_uv=False)[0]) if np.any(a) else 0.0
        assert result["numerical_rank_threshold"] == max(a.shape) * np.finfo(float).eps * scale
        assert result["least_squares_relative_cutoff"] == (max(a.shape) * np.finfo(float).eps if scale else 0.0)
        assert set(phases) == {"standard_svd_ns", "standard_qr_ns", "standard_lstsq_ns", "standard_other_ns"}
        assert contract_ns >= 0
        assert contract["solver_contract_oracle_status"] in {"UNIQUE", "INFINITE", "INCONSISTENT", "UNDECIDABLE"}
