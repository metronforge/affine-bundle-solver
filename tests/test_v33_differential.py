import json
import os
import subprocess
import sys

import pytest


def _snapshot(library):
    environment = os.environ.copy()
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                 "BLIS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        environment[name] = "4"
    output = subprocess.check_output(
        [sys.executable, "-m", "task5v33.snapshot", "--lib", library],
        env=environment, text=True)
    return json.loads(output)


@pytest.mark.skipif(not (os.environ.get("TASK5_BASELINE_SOLVER_LIB") and
                         os.environ.get("TASK5_CANDIDATE_SOLVER_LIB")),
                    reason="requires baseline and candidate solver libraries")
def test_baseline_candidate_public_witness_and_combined_differential():
    baseline = _snapshot(os.environ["TASK5_BASELINE_SOLVER_LIB"])
    candidate = _snapshot(os.environ["TASK5_CANDIDATE_SOLVER_LIB"])
    assert [row["case"] for row in baseline["records"]] == [
        row["case"] for row in candidate["records"]]
    assert [row["snapshot"] for row in baseline["records"]] == [
        row["snapshot"] for row in candidate["records"]]
