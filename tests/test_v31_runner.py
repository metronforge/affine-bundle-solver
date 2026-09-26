import json

from task5v31.runner import canonical_combined, json_safe, thermal_state, timing_invariant


def test_timing_schema_is_non_overlapping():
    row = {"timing_ns": {"materialization": 2, "standard_svd": 3, "standard_qr": 5,
                         "standard_lstsq": 7, "contract_oracle": 11, "combined_c_api": 13,
                         "validation": 17, "serialization": 19, "total_wall": 100}}
    assert timing_invariant(row, tolerance_ns=0)
    row["timing_ns"]["total_wall"] = 76
    assert not timing_invariant(row, tolerance_ns=0)


def test_json_safe_tags_nonfinite_values_without_relaxing_json():
    assert json_safe({"nan": float("nan"), "pos": float("inf"), "neg": -float("inf")}) == {
        "nan": "NaN", "pos": "Infinity", "neg": "-Infinity"}
    json.dumps(json_safe({"nan": float("nan")}), allow_nan=False)


def test_canonical_result_omits_router_relx_and_router_seconds():
    view = canonical_combined({"router_meta": list(range(11)), "certified": {}})
    assert "RELX" not in view["router_meta"]
    assert "SECONDS" not in view["router_meta"]
    assert len(view["router_meta"]) == 9


def test_thermal_snapshot_samples_one_frequency_and_all_available_zone_temperatures():
    snapshot = thermal_state()
    assert len(snapshot["frequencies_khz"]) <= 1
    assert snapshot["eligibility"] == "ELIGIBLE_NO_THROTTLE_SIGNAL"
