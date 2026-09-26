import os

import numpy as np
import pytest

from task5v31.campaign import generate_manifest
from task5v31.materialize import materialize
from task5v31.solver import call_certified, call_legacy_certified, certified_equal, router_snapshot_equal, meaningful_equal


@pytest.mark.skipif(not os.environ.get("TASK5_SOLVER_LIB"), reason="requires release solver library")
def test_combined_null_xt_matches_supplied_xt_and_reports_one_router_call():
    for slot in generate_manifest()["slots"]:
        if not slot["eligibility"]["small"]:
            continue
        a, b, _ = materialize(slot)
        null = call_certified(a, b, xt=None)
        supplied = call_certified(a, b, xt=np.linalg.lstsq(a, b, rcond=None)[0])
        assert null["api_return"] in (0, 2)
        assert null["router_executions"] == 1
        assert meaningful_equal(null, supplied)


@pytest.mark.skipif(not os.environ.get("TASK5_SOLVER_LIB"), reason="requires release solver library")
def test_combined_matches_legacy_certified_and_router_snapshot_for_small_cases():
    for slot in generate_manifest()["slots"]:
        if not slot["eligibility"]["small"]:
            continue
        a, b, _ = materialize(slot)
        combined = call_certified(a, b, xt=None)
        assert certified_equal(combined["certified"], call_legacy_certified(a, b, xt=None))
        assert router_snapshot_equal(combined, a, b)
