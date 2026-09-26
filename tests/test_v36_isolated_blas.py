import json
import math

import pytest

from task5v36.analysis import aa_decision, select_configuration
from task5v36.campaign import CAMPAIGN_ID, generate_v36_manifest
from task5v36.protocol import balanced_orders, build_schedule, run_dataset
from task5v36.runtime import CONFIGURATIONS, fingerprint_eligible, validate_telemetry


SLOTS = ("V31-025", "V31-026", "V31-027")


def test_campaign_manifest_preserves_all_27_slots_and_identity():
    manifest = generate_v36_manifest()
    assert manifest["campaign_id"] == CAMPAIGN_ID
    assert len(manifest["slots"]) == 27
    assert [slot["slot_id"] for slot in manifest["slots"]] == [
        f"V31-{index:03d}" for index in range(1, 28)
    ]


def test_calibration_configurations_are_frozen_and_role_isolated():
    c1, c2, c3 = (CONFIGURATIONS[name] for name in ("C1", "C2", "C3"))
    assert (c1.active_threads, c1.inactive_threads, c1.cpu_set) == (4, 1, "1,3,6,8")
    assert (c2.active_threads, c2.inactive_threads, c2.cpu_set) == (1, 1, "1")
    assert c3.selectable is False
    assert c3.mixed_runtime is True
    assert c1.roles["solver"].forbidden_tokens == (
        "scipy_openblas", "libmkl", "libiomp"
    )
    assert c1.roles["solver"].gomp_threads == 1
    assert c1.roles["legacy"].system_openblas_threads == 1
    assert c1.roles["legacy"].scipy_blas_threads == 4
    assert c1.roles["legacy"].mkl_threads == 1
    assert c1.roles["legacy"].iomp_threads == 1
    for policy in c3.roles.values():
        assert {
            policy.system_openblas_threads, policy.scipy_blas_threads,
            policy.mkl_threads, policy.gomp_threads, policy.iomp_threads,
        } == {4}


def test_balanced_orders_are_deterministic_and_position_balanced():
    first = balanced_orders(("M1", "M2"), repetitions=31, seed=2026093601,
                            slot_index=2)
    second = balanced_orders(("M1", "M2"), repetitions=31, seed=2026093601,
                             slot_index=2)
    assert first == second
    assert len(first) == 31
    assert abs(sum(order[0] == "M1" for order in first) -
               sum(order[0] == "M2" for order in first)) <= 1


def test_calibration_schedules_have_one_warmup_and_frozen_trial_counts():
    c1 = build_schedule("aa-C1", ("M1", "M2"), SLOTS, repetitions=31,
                        warmups=1, seed=2026093601)
    c2 = build_schedule("aa-C2", ("M1", "M2"), SLOTS, repetitions=31,
                        warmups=1, seed=2026093602)
    c3 = build_schedule("aa-C3-diagnostic", ("M1", "M2"), SLOTS,
                        repetitions=5, warmups=1, seed=2026093603)
    assert len(c1) == len(c2) == 3 * 2 * 32
    assert len(c3) == 3 * 2 * 6
    assert len({item["observation_id"] for item in c1}) == len(c1)
    for slot in SLOTS:
        for arm in ("M1", "M2"):
            rows = [item for item in c1 if item["slot_id"] == slot and
                    item["arm"] == arm]
            assert sum(item["phase"] == "warmup" for item in rows) == 1
            assert sum(item["phase"] == "eligible" for item in rows) == 31


def _telemetry(*, libraries=None, pools=None, affinity=(1, 3, 6, 8)):
    return {
        "proc_maps": ["00400000-00401000 r--p /worker"],
        "loaded_numeric_libraries": libraries or ["/usr/lib/libopenblas.so"],
        "threadpools": pools or [{"filepath": "/usr/lib/libopenblas.so",
                                   "internal_api": "openblas", "num_threads": 4}],
        "process_affinity": list(affinity),
        "process_status_threads": 4,
        "cpu_topology": [{"cpu": cpu, "core": cpu, "package": 0}
                         for cpu in affinity],
        "governors": {str(cpu): "powersave" for cpu in affinity},
        "turbo": {"enabled": True, "source": "intel_pstate/no_turbo"},
        "frequencies_khz": {str(cpu): 2_000_000 for cpu in affinity},
        "temperatures_millic": [45_000],
        "throttle": {"observed": False, "signals": {}},
        "environment": {"OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4"},
        "runtime_settings": {"libopenblas.so": {"requested": 4, "effective": 4}},
    }


def test_telemetry_and_solver_fingerprint_fail_closed():
    telemetry = _telemetry()
    validate_telemetry(telemetry)
    ok = fingerprint_eligible(telemetry, CONFIGURATIONS["C1"].roles["solver"])
    assert ok["passed"]
    contaminated = _telemetry(libraries=["/usr/lib/libopenblas.so",
                                         "/env/scipy_openblas.so"])
    assert not fingerprint_eligible(
        contaminated, CONFIGURATIONS["C1"].roles["solver"])["passed"]
    missing = dict(telemetry)
    missing.pop("proc_maps")
    with pytest.raises(ValueError, match="proc_maps"):
        validate_telemetry(missing)


def test_atomic_checkpoint_resume_never_reruns_completed_observations(tmp_path):
    schedule = build_schedule("resume", ("M1", "M2"), ("V31-025",),
                              repetitions=3, warmups=1, seed=7)
    calls = []

    def runner(item):
        calls.append(item["observation_id"])
        return {"value": len(calls)}

    checkpoint = tmp_path / "checkpoint.json"
    first = run_dataset(schedule[:3], runner=runner, checkpoint=checkpoint,
                        protocol={"name": "resume"})
    assert len(first["records"]) == 3
    second = run_dataset(schedule, runner=runner, checkpoint=checkpoint,
                         protocol={"name": "resume"})
    assert len(second["records"]) == len(schedule)
    assert calls == [item["observation_id"] for item in schedule]
    assert json.loads(checkpoint.read_text())["complete"] is True


def _aa_rows(ratio, *, order_effect=0.0, bad_fingerprint=False):
    rows = []
    for slot in SLOTS:
        for trial in range(31):
            order = ("M1", "M2") if trial % 2 == 0 else ("M2", "M1")
            shift = math.exp(order_effect if order[0] == "M2" else -order_effect)
            for arm in order:
                value = 1_000_000 if arm == "M1" else round(1_000_000 * ratio * shift)
                libraries = (["/usr/lib/libopenblas.so", "/env/libmkl_rt.so"]
                             if bad_fingerprint and arm == "M2" else None)
                rows.append({
                    "slot_id": slot, "phase": "eligible", "trial": trial,
                    "arm": arm, "order": list(order),
                    "record": {
                        "timing_ns": {"combined_c_api": value,
                                      "total_wall": value},
                        "runtime": _telemetry(libraries=libraries),
                        "thermal": {"eligibility": "ELIGIBLE"},
                        "active_compute_budget": 4,
                    },
                })
    return rows


@pytest.mark.parametrize(("ratio", "passed"), [
    (1.00, True), (1.02, True), (1.04, False), (0.90, True),
])
def test_aa_analysis_synthetic_effects(ratio, passed):
    result = aa_decision(_aa_rows(ratio), samples=2_000, seed=17,
                         configuration="C1")
    assert result["passed"] is passed


def test_aa_analysis_rejects_order_effect_and_runtime_mismatch():
    assert not aa_decision(_aa_rows(1.0, order_effect=0.03), samples=2_000,
                           seed=19, configuration="C1")["passed"]
    assert not aa_decision(_aa_rows(1.0, bad_fingerprint=True), samples=2_000,
                           seed=19, configuration="C1")["passed"]


def test_aa_analysis_fails_closed_on_missing_or_failed_observation():
    missing = _aa_rows(1.0)[:-1]
    assert not aa_decision(missing, samples=100, seed=23,
                           configuration="C1")["passed"]
    failed = _aa_rows(1.0)
    failed[-1] = {key: value for key, value in failed[-1].items()
                  if key != "record"}
    failed[-1]["execution_failure"] = {"type": "TimeoutExpired"}
    assert not aa_decision(failed, samples=100, seed=23,
                           configuration="C1")["passed"]


def test_selection_rule_uses_smallest_max_api_upper_then_e2e_tie_break():
    decisions = {
        "C1": {"passed": True, "maximum_api_upper": 1.020,
               "aggregate_main_e2e_median_ns": 100},
        "C2": {"passed": True, "maximum_api_upper": 1.024,
               "aggregate_main_e2e_median_ns": 90},
        "C3": {"passed": True, "maximum_api_upper": 0.9,
               "aggregate_main_e2e_median_ns": 1},
    }
    assert select_configuration(decisions)["selected"] == "C2"
    decisions["C2"]["maximum_api_upper"] = 1.026
    assert select_configuration(decisions)["selected"] == "C1"
