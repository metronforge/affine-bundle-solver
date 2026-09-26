import os

import pytest

from task5v32.diagnostics import build_trace_library, run_slot


@pytest.mark.skipif(not os.environ.get("TASK5_SOLVER_LIB"), reason="requires frozen solver library")
def test_preload_tracer_observes_one_router_and_native_certificate_phases(tmp_path):
    tracer = build_trace_library(tmp_path)
    trial = run_slot("V31-025", preload=tracer)
    trace = trial["trace"]
    assert "standard_oracle" not in trial["record"]
    assert trial["record"]["combined"]["router_executions"] == 1
    assert trace["router_count"] == 1
    assert trace["unique_gen_count"] == 1
    assert trace["inconsistent_gen_count"] == 1
    assert trace["verify_count"] >= 2
    assert trace["lapack_count"] > 0
    assert trace["lapack_ns"] <= trace["api_ns"]
    assert trace["router_lapack_ns"] <= trace["router_ns"]
    assert trace["generator_lapack_ns"] <= trace["unique_gen_ns"] + trace["infinite_gen_ns"] + trace["inconsistent_gen_ns"]
