import math

from task5v32.diagnostics import CAMPAIGN_ID, build_reproduction_driver, coefficient_of_variation, custom_tall_slot, diagnostic_manifest, parse_driver_csv, parse_trace_line, phase_ledger, rank_native_hotspots, reconcile_native_phases, write_binary_input


def test_manifest_is_new_identity_and_only_declares_bounded_slots():
    manifest = diagnostic_manifest()
    assert manifest["campaign_id"] == "task5-v3.2-bottleneck-20260926"
    assert [slot["slot_id"] for slot in manifest["slots"]] == ["V31-025", "V31-026", "V31-027"]
    assert manifest["solver_commit"] == "f66cd87a7b198497cc53d63b2bb04b85c3e64f53"
    assert manifest["harness_baseline"] == "1827f2d458bcf55b0ade81a1174d1fa2ceb9d9ad"


def test_trace_parser_and_reconciliation_keep_inclusive_and_exclusive_distinct():
    trace = parse_trace_line("ABS_TRACE api_ns=100 router_ns=20 unique_gen_ns=30 verify_ns=10 lapack_ns=25 api_count=1")
    assert trace["api_count"] == 1
    phases = reconcile_native_phases(trace)
    assert phases["native_total_ns"] == 100
    assert phases["router_inclusive_ns"] == 20
    assert phases["selected_kernels_inclusive_ns"] == 25
    assert phases["independent_verification_inclusive_ns"] == 10
    assert phases["native_unattributed_ns"] == 40
    assert math.isclose(phases["reconciled_fraction"], 1.0)


def test_phase_ledger_reconciles_exclusive_phases_with_end_to_end_wall():
    record = {"timing_ns": {"python_control_preparation": 5, "ffi_api_inclusive": 102,
                             "serialization_bookkeeping": 1, "total_wall": 120}}
    trace = {"api_ns": 100, "router_ns": 20, "unique_gen_ns": 30, "infinite_gen_ns": 0,
             "inconsistent_gen_ns": 0, "verify_ns": 10, "lapack_ns": 25,
             "router_lapack_ns": 5, "generator_lapack_ns": 20, "verify_lapack_ns": 0,
             "other_lapack_ns": 0}
    ledger = phase_ledger(record, trace)
    assert sum(item["exclusive_ns"] for item in ledger["phases"]) == 120
    assert ledger["unattributed_ns"] == 0


def test_native_hotspots_rank_by_inclusive_time_and_retain_call_counts():
    rows = [{"dgeqp3_ns": 90, "dgeqp3_count": 20, "dgelsy_ns": 30, "dgelsy_count": 4,
             "dgesvd_ns": 10, "dgesvd_count": 2, "dormqr_ns": 5, "dormqr_count": 2,
             "dgemm_ns": 0, "dgemm_count": 0, "dgemv_ns": 0, "dgemv_count": 0,
             "dgesdd_ns": 0, "dgesdd_count": 0}]
    ranked = rank_native_hotspots(rows, total_ns=150)
    assert ranked[0]["function"] == "dgeqp3_"
    assert ranked[0]["inclusive_median_ns"] == 90
    assert ranked[0]["call_count"] == 20
    assert ranked[0]["share_of_end_to_end"] == 0.6


def test_custom_tall_slot_changes_only_dimensions_and_identity():
    slot = custom_tall_slot(192, 96)
    assert slot["slot_id"] == "V32-TALL-192x96"
    assert (slot["m"], slot["n"]) == (192, 96)
    assert slot["structural_rank_profile"]["algebraic_rank"] == 96
    assert slot["generator_parameters"]["profile"] == "full"
    assert slot["rhs_policy"] == "compatible"


def test_standalone_reproduction_driver_builds_and_input_is_size_bounded(tmp_path):
    executable = build_reproduction_driver(tmp_path)
    input_path = write_binary_input(tmp_path / "v31-027.bin", custom_tall_slot(256, 128))
    assert executable.is_file()
    assert input_path.stat().st_size == 8 + (256 * 128 + 256) * 8


def test_driver_csv_and_variance_summary_are_numeric():
    rows = parse_driver_csv("trial,combined_ns,router_ns\n0,100,20\n1,110,21\n")
    assert rows == [{"trial": 0, "combined_ns": 100, "router_ns": 20},
                    {"trial": 1, "combined_ns": 110, "router_ns": 21}]
    assert coefficient_of_variation([100, 100, 100]) == 0.0
