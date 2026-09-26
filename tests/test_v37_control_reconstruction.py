from task5v36.runtime import CONFIGURATIONS
from task5v36.protocol import build_schedule
from task5v37 import CAMPAIGN_ID
from task5v37.runtime import bootstrap_environment


def test_legacy_bootstraps_scipy_openblas_at_active_budget():
    policy = CONFIGURATIONS["C1"].roles["legacy"]
    environment = bootstrap_environment(policy)
    assert environment["OPENBLAS_NUM_THREADS"] == "4"


def test_solver_bootstrap_remains_at_active_system_openblas_budget():
    policy = CONFIGURATIONS["C1"].roles["solver"]
    environment = bootstrap_environment(policy)
    assert environment["OPENBLAS_NUM_THREADS"] == "4"
    assert environment["OMP_NUM_THREADS"] == "1"


def test_v37_campaign_identity_and_frozen_schedule():
    assert CAMPAIGN_ID == "task5-v3.7-reconstructed-control-20260926"
    schedule = build_schedule("qualification-v3.7", ("L", "M", "A"),
                              ("V31-025", "V31-026", "V31-027"),
                              repetitions=31, warmups=1, seed=2026093704)
    assert len(schedule) == 288
    assert sum(row["phase"] == "eligible" for row in schedule) == 279
    assert len({row["observation_id"] for row in schedule}) == 288
