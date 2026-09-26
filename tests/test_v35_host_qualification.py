import math

from task5v35.analysis import (aa_decision, aggregate_speedup, compare_paired,
                               official_decision, qualification_gate)
from task5v35.protocol import (ARMS, balanced_orders, run_dataset, run_dense_dataset,
                               trial_command)
from task5v35.dense import dense_input, dense_manifest


def _rows(reference_ns, candidate_ns, slot="V31-025"):
    records = []
    for trial, (left, right) in enumerate(zip(reference_ns, candidate_ns, strict=True)):
        for arm, value in (("M", left), ("A", right)):
            records.append({
                "slot_id": slot,
                "phase": "eligible",
                "trial": trial,
                "arm": arm,
                "order": ["M", "A"] if trial % 2 == 0 else ["A", "M"],
                "record": {
                    "timing_ns": {"combined_c_api": value, "total_wall": value},
                    "peak_rss_kb": 100,
                    "combined": {"router_executions": 1},
                },
            })
    return records


def test_balanced_four_arm_order_has_31_trials_and_maximum_position_imbalance_one():
    orders = balanced_orders(("L", "M", "F", "A"), repetitions=31,
                             seed=20260926, slot_index=0)
    assert len(orders) == 31
    assert len(set(orders)) > 1
    for arm in ("L", "M", "F", "A"):
        counts = [sum(order[pos] == arm for order in orders) for pos in range(4)]
        assert max(counts) - min(counts) <= 1


def test_paired_noninferiority_synthetic_equality_and_two_percent_regression_pass():
    equal = compare_paired(_rows([100] * 31, [100] * 31), "M", "A",
                           "combined_c_api", samples=2_000, seed=7)
    two_percent = compare_paired(_rows([100] * 31, [102] * 31), "M", "A",
                                 "combined_c_api", samples=2_000, seed=7)
    assert equal["ratio_point"] == 1.0
    assert equal["one_sided_95_upper"] < 1.03
    assert math.isclose(two_percent["ratio_point"], 1.02)
    assert two_percent["one_sided_95_upper"] < 1.03


def test_paired_noninferiority_synthetic_four_percent_regression_fails():
    result = compare_paired(_rows([100] * 31, [104] * 31), "M", "A",
                            "combined_c_api", samples=2_000, seed=7)
    assert math.isclose(result["ratio_point"], 1.04)
    assert result["one_sided_95_upper"] >= 1.03


def test_clear_improvement_and_aggregate_speedup_are_reported():
    all_records = []
    for slot in ("V31-025", "V31-026", "V31-027"):
        rows = _rows([200] * 31, [100] * 31, slot)
        for row in rows:
            row["arm"] = "L" if row["arm"] == "M" else row["arm"]
            row["order"] = ["L" if item == "M" else item for item in row["order"]]
        all_records.extend(rows)
    aggregate = aggregate_speedup(all_records, "L", "A", "total_wall",
                                  samples=2_000, seed=11)
    assert aggregate["point_speedup"] == 2.0
    assert aggregate["bootstrap_95_ci"] == [2.0, 2.0]


def test_qualification_gate_requires_every_frozen_predicate():
    checks = {
        "correctness": True,
        "router_once": True,
        "complete_eligible_set": True,
        "v25_api_noninferior": True,
        "no_e2e_regression_over_10_percent": True,
        "legacy_candidate_geomean_at_least_1_5": True,
        "rss_within_10_percent": True,
        "thermal_valid": True,
        "production_api_gain": True,
        "integrity": True,
    }
    assert qualification_gate(checks)["passed"]
    checks["v25_api_noninferior"] = False
    assert not qualification_gate(checks)["passed"]


def test_trial_command_pins_affinity_and_only_legacy_arm_supplies_xt(tmp_path):
    libraries = {arm: tmp_path / f"{arm}.so" for arm in ARMS}
    legacy = trial_command("V31-025", "L", libraries, cpu_set="1,3,6,8")
    candidate = trial_command("V31-025", "A", libraries, cpu_set="1,3,6,8")
    assert legacy[:3] == ["taskset", "-c", "1,3,6,8"]
    assert "--legacy-preliminary-xt" in legacy
    assert "--legacy-preliminary-xt" not in candidate


def test_official_dataset_has_one_warmup_and_31_observations_per_arm_slot(monkeypatch):
    calls = []

    def fake_trial(slot_id, arm, libraries, *, cpu_set, thread_values):
        calls.append((slot_id, arm, cpu_set, dict(thread_values)))
        return {"slot_id": slot_id, "combined": {"router_executions": 1},
                "timing_ns": {"combined_c_api": 1, "total_wall": 2},
                "peak_rss_kb": 1}

    monkeypatch.setattr("task5v35.protocol.execute_trial", fake_trial)
    report = run_dataset({arm: f"/{arm}.so" for arm in ARMS}, repetitions=31,
                         warmups=1, seed=20260926, cpu_set="1,3,6,8")
    assert len(report["records"]) == 3 * len(ARMS) * 32
    for slot in ("V31-025", "V31-026", "V31-027"):
        for arm in ARMS:
            rows = [row for row in report["records"]
                    if row["slot_id"] == slot and row["arm"] == arm]
            assert sum(row["phase"] == "warmup" for row in rows) == 1
            assert sum(row["phase"] == "eligible" for row in rows) == 31
    assert all(call[2] == "1,3,6,8" for call in calls)
    assert all(set(call[3].values()) == {"4"} for call in calls)


def test_aa_decision_accepts_equal_builds_and_rejects_four_percent_bias():
    equal = _rows([100] * 31, [100] * 31)
    biased = _rows([100] * 31, [104] * 31)
    for rows in (equal, biased):
        for row in rows:
            row["arm"] = "M1" if row["arm"] == "M" else "M2"
            row["order"] = ["M1" if x == "M" else "M2" for x in row["order"]]
            row["record"]["loaded_numeric_libraries"] = ["/usr/lib/libopenblas.so"]
    assert aa_decision(equal, samples=2_000, seed=9)["passed"]
    assert not aa_decision(biased, samples=2_000, seed=9)["passed"]


def test_official_decision_accepts_direct_two_x_legacy_speedup():
    records = []
    timings = {"L": 200, "M": 120, "F": 115, "A": 100}
    for slot in ("V31-025", "V31-026", "V31-027"):
        for trial in range(31):
            order = ["L", "M", "F", "A"]
            for arm in order:
                records.append({
                    "slot_id": slot, "phase": "eligible", "trial": trial,
                    "arm": arm, "order": order,
                    "record": {
                        "matrix": {"m": 1, "n": 1},
                        "combined": {"router_executions": 1, "status": "UNIQUE"},
                        "timing_ns": {"combined_c_api": timings[arm],
                                      "total_wall": timings[arm]},
                        "peak_rss_kb": 100,
                        "thermal": {"eligibility": "ELIGIBLE_NO_THROTTLE_SIGNAL"},
                        "loaded_numeric_libraries": ["/usr/lib/libopenblas.so"],
                        "process_affinity": [1, 3, 6, 8],
                    },
                })
    result = official_decision(records, samples=2_000, seed=13, integrity=True)
    assert result["aggregate_legacy_candidate"]["point_speedup"] == 2.0
    assert result["passed"]


def test_dense_secondary_inputs_are_deterministic_and_use_frozen_shapes():
    left_a, left_b = dense_input("V31-027")
    right_a, right_b = dense_input("V31-027")
    assert left_a.shape == (256, 128)
    assert left_b.shape == (256,)
    assert (left_a == right_a).all()
    assert (left_b == right_b).all()
    assert (left_b == left_a[:, 0]).all()
    manifest = dense_manifest()
    assert manifest["V31-027"]["seed"] == 20260929
    assert len(manifest["V31-027"]["matrix_sha256"]) == 64


def test_dense_secondary_protocol_is_one_warmup_plus_11_trials(monkeypatch):
    monkeypatch.setattr(
        "task5v35.protocol.execute_dense_trial",
        lambda slot_id, arm, libraries, **kwargs: {
            "slot_id": slot_id, "combined": {"router_executions": 1},
            "timing_ns": {"combined_c_api": 1, "total_wall": 1},
            "peak_rss_kb": 1,
        },
    )
    report = run_dense_dataset({"M": "/M.so", "A": "/A.so"},
                               seed=20260930, cpu_set="1,3,6,8")
    assert len(report["records"]) == 3 * 2 * 12
    assert report["protocol"]["eligible_trials_per_arm_slot"] == 11


def test_explicit_thread_matrix_values_are_recorded_and_forwarded(monkeypatch):
    seen = []

    def fake_trial(slot_id, arm, libraries, *, cpu_set, thread_values):
        seen.append(dict(thread_values))
        return {"slot_id": slot_id, "combined": {"router_executions": 1},
                "timing_ns": {"combined_c_api": 1, "total_wall": 1},
                "peak_rss_kb": 1}

    monkeypatch.setattr("task5v35.protocol.execute_trial", fake_trial)
    thread_values = {name: "1" for name in (
        "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
        "BLIS_NUM_THREADS", "NUMEXPR_NUM_THREADS")}
    report = run_dataset({"M": "/M.so"}, repetitions=1, warmups=0,
                         seed=1, cpu_set="0-21", arms=("M",),
                         slots=("V31-025",), thread_values=thread_values)
    assert report["protocol"]["thread_environment"] == thread_values
    assert seen == [thread_values]
