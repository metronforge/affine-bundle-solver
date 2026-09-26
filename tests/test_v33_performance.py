import math


def test_comparison_uses_frozen_control_candidate_libraries_and_five_trials(monkeypatch, tmp_path):
    from task5v33 import performance

    calls = []

    def fake_trial(slot_id, path, library, environment):
        calls.append((slot_id, path, library, dict(environment)))
        elapsed = 200 if path == "control" else 100
        return {
            "campaign_id": performance.CAMPAIGN_ID,
            "slot_id": slot_id,
            "matrix": {"m": 1, "n": 1},
            "router_strategy": "clear_full_rank",
            "standard_oracle": {"status": "UNIQUE"},
            "contract_oracle": {"status": "UNIQUE"},
            "combined": {"router_executions": 1, "api_return": 0},
            "timing_ns": {"total_wall": elapsed, "combined_c_api": elapsed // 2},
            "peak_rss_kb": 100,
            "thermal": {"eligibility": "ELIGIBLE_NO_THROTTLE_SIGNAL"},
        }

    monkeypatch.setattr(performance, "_trial", fake_trial)
    report = performance.run_comparison(
        ["V31-025", "V31-026", "V31-027"],
        baseline_library=tmp_path / "baseline.so",
        candidate_library=tmp_path / "candidate.so",
        repetitions=5,
    )

    # Two excluded warmups and ten alternating eligible executions per slot.
    assert len(calls) == 36
    assert all(call[3][name] == "4" for call in calls for name in performance.THREAD_VARIABLES)
    assert all(call[2].name == ("baseline.so" if call[1] == "control" else "candidate.so") for call in calls)
    assert all(summary["eligible_trials"] == 5 for summary in report["summaries"])
    assert all(summary["semantic_agreement"] for summary in report["summaries"])
    assert all(summary["candidate_router_executions"] == [1] for summary in report["summaries"])
    assert math.isclose(report["geometric_mean_speedup"], 2.0)
    assert report["pre_gate"]["passed"]


def test_semantic_view_excludes_only_measurement_and_path_fields():
    from task5v33.performance import semantic_view

    row = {
        "campaign_id": "x",
        "path": "candidate",
        "library": "candidate.so",
        "timing_ns": {"total_wall": 1},
        "cpu_time_ns": 2,
        "peak_rss_kb": 3,
        "thermal": {"eligibility": "x"},
        "thread_configuration": {"OMP_NUM_THREADS": "4"},
        "legacy_preliminary_lstsq_ns": 0,
        "matrix": {"m": 2, "n": 1},
        "combined": {"router_executions": 1},
    }
    assert semantic_view(row) == {"matrix": {"m": 2, "n": 1}, "combined": {"router_executions": 1}}
