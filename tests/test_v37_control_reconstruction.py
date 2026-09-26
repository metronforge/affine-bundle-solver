from task5v36.runtime import CONFIGURATIONS
from task5v36.protocol import build_schedule
from task5v37 import CAMPAIGN_ID
from task5v37.runtime import bootstrap_environment
from task5v37.validation import BASE_ENV
from task5v37.audit import coefficient_of_variation, order_summary, schedule_matches


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


def test_validation_environment_is_deterministic_and_inactive_runtimes_are_one():
    assert BASE_ENV["OMP_NUM_THREADS"] == "1"
    assert BASE_ENV["MKL_NUM_THREADS"] == "1"
    assert BASE_ENV["OMP_DYNAMIC"] == "FALSE"
    assert BASE_ENV["PYTHONHASHSEED"] == "0"


def test_order_and_variance_audit_on_equal_pairs():
    pairs = [(10, 10, ("L", "A")), (20, 20, ("A", "L"))]
    result = order_summary(pairs, "L", "A")
    assert result["candidate_before_reference_n"] == 1
    assert result["candidate_after_reference_n"] == 1
    assert result["log_ratio_difference"] == 0.0
    assert coefficient_of_variation([5, 5, 5]) == 0.0


def test_schedule_match_handles_warmup_and_eligible_specific_keys():
    schedule = [
        {"observation_id": "warm", "phase": "warmup", "warmup": 0},
        {"observation_id": "trial", "phase": "eligible", "trial": 0},
    ]
    records = [dict(schedule[0], record={"value": 1}),
               dict(schedule[1], record={"value": 2})]
    assert schedule_matches(records, schedule)
