import pytest

from task5v34.performance import bootstrap_median_ratio_ci, coefficient_of_variation, mad, summarize_pairs


def test_dispersion_statistics_are_deterministic():
    assert mad([8, 10, 12]) == 2
    assert coefficient_of_variation([10, 10, 10]) == 0.0


def test_paired_summary_reports_api_and_end_to_end_speedups():
    control = [
        {"timing_ns": {"combined_c_api": 80, "total_wall": 100}, "peak_rss_kb": 100},
        {"timing_ns": {"combined_c_api": 88, "total_wall": 110}, "peak_rss_kb": 102},
        {"timing_ns": {"combined_c_api": 72, "total_wall": 90}, "peak_rss_kb": 98},
    ]
    candidate = [
        {"timing_ns": {"combined_c_api": 40, "total_wall": 50}, "peak_rss_kb": 99},
        {"timing_ns": {"combined_c_api": 44, "total_wall": 55}, "peak_rss_kb": 101},
        {"timing_ns": {"combined_c_api": 36, "total_wall": 45}, "peak_rss_kb": 97},
    ]
    summary = summarize_pairs(control, candidate, bootstrap_samples=500)
    assert summary["api"]["median_speedup"] == 2.0
    assert summary["end_to_end"]["median_speedup"] == 2.0
    assert summary["end_to_end"]["paired_ratios"] == [2.0, 2.0, 2.0]
    assert summary["rss_ratio"] == pytest.approx(99 / 100)


def test_bootstrap_interval_is_order_stable_and_contains_constant_ratio():
    left = bootstrap_median_ratio_ci([2.0] * 11, samples=1000, seed=20260926)
    right = bootstrap_median_ratio_ci([2.0] * 11, samples=1000, seed=20260926)
    assert left == right == [2.0, 2.0]
