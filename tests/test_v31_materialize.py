import numpy as np

from task5v31.campaign import generate_manifest
from task5v31.materialize import materialize


def test_compatible_rhs_is_constructed_without_a_matrix_product():
    for slot in generate_manifest()["slots"]:
        a, b, metadata = materialize(slot)
        assert a.shape == (slot["m"], slot["n"])
        assert b.shape == (slot["m"],)
        if slot["rhs_policy"] == "compatible":
            np.testing.assert_array_equal(b, a.sum(axis=1))
        assert metadata["algebraic_rank"] == slot["structural_rank_profile"]["algebraic_rank"]
