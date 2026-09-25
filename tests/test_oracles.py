import numpy as np
import pytest

from task5v3.campaign import generate_manifest
from task5v3.materialize import materialize
from task5v3.oracles import contract_oracle, standard_oracle


def _slot(profile, rhs="compatible", shape="square"):
    return next(s for s in generate_manifest()["slots"]
                if s["generator_parameters"]["profile"] == profile
                and s["rhs_policy"] == rhs and s["shape_class"] == shape
                and s["eligibility"]["small"])


def test_materializer_preserves_analytic_rank_and_rhs_policy():
    for slot in generate_manifest()["slots"]:
        if not slot["eligibility"]["small"]:
            continue
        a, b, meta = materialize(slot)
        assert a.shape == (slot["m"], slot["n"])
        assert b.shape == (slot["m"],)
        assert np.isfinite(a).all() and np.isfinite(b).all()
        rank = slot["structural_rank_profile"]["algebraic_rank"]
        if slot["rhs_policy"] == "compatible":
            np.testing.assert_allclose(b, a @ np.ones(slot["n"]), rtol=0, atol=0)
        else:
            assert b[rank] == 1.0 and np.all(a[rank] == 0)
        assert meta["algebraic_rank"] == rank


@pytest.mark.parametrize("scale", [1.0, 1e8])
def test_scaled_diag_uses_relative_lstsq_cutoff(scale):
    slot = next(s for s in generate_manifest()["slots"]
                if s["generator_parameters"]["profile"] == "scaled_pair"
                and s["generator_parameters"]["scale"] == scale)
    a, b, _ = materialize(slot)
    np.testing.assert_array_equal(a, scale * np.diag([1.0, 1e-10]))
    result, phases = standard_oracle(a, b, slot)
    assert result["standard_numerical_oracle_status"] == "UNIQUE"
    assert result["rank_svd"] == 2 and result["rank_qr"] == 2
    assert result["lstsq_rank"] == 2
    assert result["least_squares_relative_cutoff"] == 2 * np.finfo(float).eps
    assert result["numerical_rank_threshold"] == 2 * np.finfo(float).eps * scale
    assert set(phases) == {"standard_svd_ns", "standard_qr_ns", "standard_lstsq_ns", "standard_other_ns"}


@pytest.mark.parametrize("mode", ["FULL", "QR"])
def test_exact_deficiency_zero_and_incompatibility(mode):
    slot = dict(_slot("exact_deficient"))
    slot["standard_oracle_mode"] = mode
    a, b, _ = materialize(slot)
    compatible, _ = standard_oracle(a, b, slot)
    assert compatible["standard_numerical_oracle_status"] == "INFINITE"
    assert compatible["rank_qr"] == 3
    assert compatible["rank_svd"] == (3 if mode == "FULL" else None)
    bad_slot = dict(_slot("exact_deficient", "incompatible"))
    bad_slot["standard_oracle_mode"] = mode
    a, b, _ = materialize(bad_slot)
    incompatible, _ = standard_oracle(a, b, bad_slot)
    assert incompatible["standard_numerical_oracle_status"] == "INCONSISTENT"
    for rhs, expected in (("compatible", "INFINITE"), ("incompatible", "INCONSISTENT")):
        zero_slot = dict(_slot("zero", rhs))
        zero_slot["standard_oracle_mode"] = mode
        a, b, _ = materialize(zero_slot)
        result, _ = standard_oracle(a, b, zero_slot)
        assert result["standard_numerical_oracle_status"] == expected
        assert result["least_squares_relative_cutoff"] == 0.0
        assert result["numerical_rank_threshold"] == 0.0


@pytest.mark.parametrize("mode", ["FULL", "QR"])
def test_threshold_neighborhood_and_repetition(mode):
    eps = np.finfo(float).eps
    for factor, expected_rank in ((0.5, 1), (2.0, 2)):
        a = np.diag([1.0, factor * 2 * eps])
        b = np.zeros(2)
        slot = {"standard_oracle_mode": mode}
        one, _ = standard_oracle(a, b, slot)
        two, _ = standard_oracle(a, b, slot)
        assert one == two
        assert one["rank_qr"] == expected_rank
        assert one["rank_svd"] == (expected_rank if mode == "FULL" else None)


def test_contract_oracle_is_deterministic_for_clear_small_case():
    a, b, _ = materialize(_slot("full", shape="tall"))
    one, elapsed = contract_oracle(a, b)
    two, _ = contract_oracle(a, b)
    assert elapsed >= 0
    assert one == two
    assert one["solver_contract_oracle_status"] == "UNIQUE"
