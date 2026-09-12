#!/usr/bin/env python3
"""Fixture-only adversarial tests for numerical-suite evidence contracts."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from experiments import numerical_suite_contract as contract
except ImportError:
    contract = None

import check_paper_claims


EXPECTED_SECTIONS = (
    ("standard", "standard"),
    ("rank", "rank_transition"),
    ("guard", "guard_timing"),
    ("scaling", "scaling"),
    ("structural", "structural"),
    ("lapack", "lapack_context"),
)

EXPECTED_CASE_IDS = {
    "standard": (
        "standard.random64", "standard.grouped64", "standard.rankdef64",
        "standard.inconsistent64", "standard.digits", "standard.random128",
        "standard.grouped256", "standard.rankdef256", "standard.random512",
    ),
    "rank": (
        "rank.eps_1e-08", "rank.eps_3e-09", "rank.eps_1e-09",
        "rank.eps_3e-10", "rank.eps_3e-11", "rank.eps_1e-12",
    ),
    "guard": (
        "guard.2000x64.r63", "guard.10000x64.r63",
        "guard.50000x64.r63", "guard.5000x96.r95",
        "guard.20000x96.r95", "guard.10000x64.r32",
        "guard.10000x64.r1", "guard.512x192.r191",
    ),
    "scaling": tuple(
        f"scaling.omp{threads}.{name}"
        for threads in (1, 2, 4)
        for name in ("grouped64", "rankdef64", "grouped256")
    ),
    "structural": tuple(
        case_id
        for n in (32, 64, 128, 256, 512)
        for mult in (4, 16, 64)
        for case_id in (f"structural.full_n{n}_x{mult}",
                        f"structural.def_n{n}_x{mult}")
    ) + tuple(f"structural.late_n128_r0_{rank}"
              for rank in (1, 2, 4, 8, 16, 64)) + (
        "structural.delayed_n64", "structural.delayed_n128",
        "structural.inconsistent_n64", "structural.inconsistent_n128",
        "structural.scaled_n64_r64", "structural.scaled_n64_r56",
        "structural.scaled_n128_r128", "structural.scaled_n128_r112",
    ),
    "lapack": (
        "lapack.random64", "lapack.grouped64", "lapack.rankdef64",
        "lapack.random128", "lapack.rankdef256", "lapack.random512",
    ),
}

EXACT_BLOCKERS = {
    "manuscript_blocker:audit.certified_call_overhead",
    "manuscript_blocker:standard.sequential_reference",
    "manuscript_blocker:parallel.openmp_scaling",
    "manuscript_blocker:structural.stress_timings",
    "manuscript_blocker:transition.rank_gate",
    "manuscript_blocker:guard.rank1_cost",
    "manuscript_blocker:well1033.performance",
    "manuscript_blocker:contextual.dgelsy",
    "manuscript_blocker:wide_extreme.32x12800",
    "manuscript_blocker:wide_extreme.lp_fit2d",
    "manuscript_blocker:grouped.lsmr",
    "manuscript_blocker:limitations.square_underdetermined",
    "manuscript_blocker:applications.radio_timings",
    "manuscript_blocker:applications.harmonic_timings",
    "manuscript_blocker:applications.lens_timings",
    "manuscript_blocker:parallel.bundle_tree_late_growth",
    "manuscript_blocker:methodology.quantitative_results_freshness",
    "manuscript_blocker:methodology.json_environment_raw_outputs",
}


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha_file(path):
    return sha_bytes(Path(path).read_bytes())


def load_runner_module():
    spec = importlib.util.spec_from_file_location(
        "fixture_numerical_runner", ROOT / "experiments/rerun_numerical_suite.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ContractTestCase(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            contract, "experiments.numerical_suite_contract is not implemented")

    def input_record(self, case_id, seed=None):
        spec = contract.CANONICAL_CASES_BY_ID[case_id]
        m, n = spec["m"], spec["n"]
        seed = spec["input_seeds"][0] if seed is None else seed
        record = {
            "generator": spec["generator"], "seed": seed,
            "m": m, "n": n, "dtype": "float64", "byte_order": "native",
            "layout": "row-major", "c_contiguous": True,
            "strides": [n * 8, 8],
            "sha256": {"A": "a" * 64, "b": "b" * 64, "x": "c" * 64},
        }
        if case_id == "standard.digits":
            record["sha256"]["A"] = contract.DIGITS_DESIGN_SHA256
        return record

    def timing(self, spec, offset=1.0):
        raw = [offset + index for index in range(spec["repetitions"])]
        median = float(np.median(raw))
        mad = float(np.median(np.abs(np.asarray(raw) - median)))
        return {
            "operation": spec["operation"], "source": spec["source"],
            "unit": "seconds", "warmups": spec["warmups"],
            "repetitions": spec["repetitions"], "raw": raw,
            "median": median, "mad": mad,
        }

    def result_document(self, sections=None):
        rows = []
        chosen = sections or [name for name, _ in EXPECTED_SECTIONS]
        for section_name in chosen:
            cases = []
            for case_id in EXPECTED_CASE_IDS[section_name]:
                spec = contract.CANONICAL_CASES_BY_ID[case_id]
                expected = {"status": spec["expected_status"],
                            "rank": spec["expected_rank"]}
                if section_name == "rank":
                    expected["rank_interval"] = [
                        spec["expected_rank_lo"], spec["expected_rank_hi"]]
                cases.append({
                    "case_id": case_id,
                    "inputs": [self.input_record(case_id, seed)
                               for seed in spec["input_seeds"]],
                    "timings": [self.timing(item, index + 1.0)
                                for index, item in enumerate(spec["timings"])],
                    "diagnostics": {
                        "status": spec["expected_status"],
                        "rank": spec["expected_rank"],
                        "rank_lo": spec["expected_rank_lo"],
                        "rank_hi": spec["expected_rank_hi"],
                        "router_relres": None, "router_berr": None,
                    },
                    "numerical_contract": {
                        "expected": expected,
                        "actual": {"status": spec["expected_status"],
                                   "rank": spec["expected_rank"]},
                        "valid": True, "reasons": [],
                    },
                    "observations": {"timing_range": "not-evaluated"},
                })
            summary = {"case_count": len(cases)}
            if section_name == "structural":
                summary.update({"hard_failure_count": 0,
                                "reported_hard_failure_count": 0})
            rows.append({"section_id": section_name,
                         "output_name": dict(EXPECTED_SECTIONS)[section_name],
                         "cases": cases, "summary": summary})
        return {
            "schema_version": 2,
            "protocol_id": "affine-bundle-numerical-suite-v2",
            "protocol_signature": contract.PROTOCOL_SIGNATURE,
            "sections": rows,
            "numerical_contract": {"valid": True, "reasons": []},
        }

    def metadata_document(self, result_bytes=b"{}"):
        return {
            "schema_version": 2,
            "scope": "reference-machine-numerical-evidence",
            "reference_machine_id": "metronforge-laptop-ref-test",
            "result": {
                "filename": "numerical-suite-reference.json",
                "sha256": sha_bytes(result_bytes), "schema_version": 2,
                "protocol_id": "affine-bundle-numerical-suite-v2",
                "protocol_signature": contract.PROTOCOL_SIGNATURE,
            },
            "source": {
                "before": {"git_sha": "1" * 40, "git_tree_sha": "2" * 40,
                           "git_dirty": False},
                "after": {"git_sha": "1" * 40, "git_tree_sha": "2" * 40,
                          "git_dirty": False},
            },
            "generator": {"path": "experiments/rerun_numerical_suite.py",
                          "sha256": "3" * 64},
            "dependency_locks": [
                {"path": "requirements-numerical-suite.txt",
                 "sha256": "4" * 64},
                {"path": "requirements-ci.txt", "sha256": "5" * 64},
            ],
            "command": {
                "executable_basename": "python3",
                "argv": ["experiments/rerun_numerical_suite.py", "--candidate",
                         "--reference-machine", "metronforge-laptop-ref-test"],
            },
            "run": {"started_utc": "2026-09-12T10:00:00Z",
                    "ended_utc": "2026-09-12T10:01:00Z",
                    "duration_seconds": 60.0},
            "build": {
                "manifest_schema_version": 1,
                "manifest_sha256": "6" * 64,
                "built_at_utc": "2026-09-12T09:55:00Z",
                "source": {"git_sha": "1" * 40, "git_tree_sha": "2" * 40,
                           "git_dirty": False},
                "build_script": {"path": "build.sh", "sha256": "7" * 64},
                "compiler": {"identity": "gcc test", "command_argv": ["gcc"]},
                "router": {"basename": "libaffine_bundle_solver.so",
                           "sha256": "8" * 64,
                           "compile_argv": ["gcc", "-O3", "-c"],
                           "link_argv": ["gcc", "-shared", "libblas.so"],
                           "arch_flags": ""},
                "linked_blas": {"basename": "libblas.so", "sha256": "9" * 64},
            },
            "runtime": {
                "loaded_router": {"basename": "libaffine_bundle_solver.so",
                                  "sha256": "8" * 64},
                "blas_pools": [{"basename": "libblas.so", "sha256": "9" * 64,
                                "user_api": "blas", "internal_api": "openblas",
                                "num_threads": 1, "version": "test"}],
                "thread_controls": {
                    "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "1",
                    "MKL_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1",
                },
                "openmp_schedule": [1, 2, 4],
            },
            "machine": {"cpu_model": "Test CPU", "physical_cores": 4,
                        "logical_cores": 8, "ram_bytes": 1024,
                        "os": "Linux", "kernel": "test"},
            "software": {
                "python": "3.12", "numpy": "2.5.3", "scipy": "1.18.1",
                "scikit-learn": "1.9.1", "threadpoolctl": "3.6.0",
                "mpmath": "1.4.1", "joblib": "1.6.0",
                "cloudpickle": "3.1.2", "narwhals": "2.26.0",
            },
            "evidence_eligibility": {"eligible": True, "reasons": []},
        }


class ProtocolTests(ContractTestCase):
    def test_protocol_has_literal_section_and_case_order(self):
        self.assertEqual(contract.CANONICAL_SECTIONS, EXPECTED_SECTIONS)
        self.assertEqual(contract.CANONICAL_CASE_IDS, EXPECTED_CASE_IDS)
        self.assertEqual(sum(map(len, EXPECTED_CASE_IDS.values())), 82)
        self.assertRegex(contract.PROTOCOL_SIGNATURE, r"^[0-9a-f]{64}$")

    def test_rank_transition_expectations_are_signed(self):
        first = contract.CANONICAL_CASES_BY_ID["rank.eps_1e-08"]
        last = contract.CANONICAL_CASES_BY_ID["rank.eps_1e-12"]
        self.assertEqual((first["expected_status"], first["expected_rank"],
                          first["expected_rank_lo"], first["expected_rank_hi"]),
                         ("unique", 256, 256, 256))
        self.assertEqual((last["expected_status"], last["expected_rank"],
                          last["expected_rank_lo"], last["expected_rank_hi"]),
                         ("undecidable", 255, 255, 256))

    def test_sections_fail_before_computation_for_bad_candidate_sets(self):
        exact = ",".join(name for name, _ in EXPECTED_SECTIONS)
        self.assertEqual(contract.parse_sections(exact, candidate=True),
                         tuple(name for name, _ in EXPECTED_SECTIONS))
        for value in ("standard,rank", "standard,unknown",
                      "standard,rank,guard,guard,structural,lapack",
                      "rank,standard,guard,scaling,structural,lapack"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                contract.parse_sections(value, candidate=True)

    def test_partial_diagnostic_is_valid_data_but_ineligible(self):
        result = self.result_document(["standard", "rank"])
        verdict = contract.evaluate_eligibility(
            result=result, metadata=self.metadata_document(),
            candidate=False, omp=4)
        self.assertFalse(verdict["eligible"])
        self.assertIn("partial_diagnostic_run", verdict["reasons"])


class InputAndTimingTests(ContractTestCase):
    def test_describe_input_checks_abi_and_hashes_canonical_bytes(self):
        A = np.ascontiguousarray([[1.0, 2.0], [3.0, 4.0]])
        b = np.ascontiguousarray([5.0, 6.0])
        x = np.ascontiguousarray([7.0, 8.0])
        record = contract.describe_input(A, b, x, generator="fixture", seed=7)
        self.assertEqual(record["dtype"], "float64")
        self.assertEqual(record["byte_order"], "native")
        self.assertEqual(record["layout"], "row-major")
        self.assertEqual(record["strides"], [16, 8])
        self.assertEqual(record["sha256"]["A"], sha_bytes(A.tobytes(order="C")))
        self.assertEqual(record["sha256"]["b"], sha_bytes(b.tobytes(order="C")))
        self.assertEqual(record["sha256"]["x"], sha_bytes(x.tobytes(order="C")))

    def test_abi_rejects_dtype_byteorder_shape_strides_and_layout(self):
        A = np.eye(2, dtype=np.float64)
        b = np.ones(2, dtype=np.float64)
        x = np.ones(2, dtype=np.float64)
        bad = ((A.astype(np.float32), b, x), (A.astype(">f8"), b, x),
               (A, b.reshape(2, 1), x),
               (np.ones((2, 4), dtype=np.float64)[:, ::2], b, x),
               (np.asfortranarray(A), b, x))
        for arrays in bad:
            with self.subTest(strides=arrays[0].strides), self.assertRaises(ValueError):
                contract.describe_input(*arrays, generator="fixture", seed=1)

    def test_timing_record_validates_raw_count_and_recomputes_median_mad(self):
        record = contract.timing_record(
            operation="router", source="solver-reported", warmups=3,
            repetitions=3, raw=[1.0, 3.0, 2.0])
        self.assertEqual((record["median"], record["mad"]), (2.0, 1.0))
        for raw in ([], [1.0, 2.0], [0.0, 1.0, 2.0],
                    [math.nan, 1.0, 2.0], [math.inf, 1.0, 2.0]):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                contract.timing_record(operation="router", source="solver-reported",
                                       warmups=3, repetitions=3, raw=raw)

    def test_ratio_has_explicit_name_direction_and_value(self):
        self.assertEqual(contract.ratio_record(
            name="sequential_reference_over_router",
            numerator_operation="sequential_reference",
            denominator_operation="router", numerator=4, denominator=2), {
                "name": "sequential_reference_over_router",
                "direction": "sequential_reference/router", "value": 2.0})


class ResultValidationTests(ContractTestCase):
    def test_valid_result_passes_and_legacy_is_rejected(self):
        self.assertEqual(contract.validate_result_document(self.result_document()), [])
        legacy = json.loads((ROOT / "results/numerical_final_suite.json").read_text())
        reasons = contract.validate_result_document(legacy)
        self.assertIn("result_schema_version_invalid", reasons)
        self.assertIn("result_protocol_signature_missing", reasons)
        self.assertIn("result_raw_timings_missing", reasons)

    def test_result_rejects_schema_signature_and_section_damage(self):
        mutations = []
        schema = self.result_document(); schema["schema_version"] = 1
        mutations.append((schema, "result_schema_version_invalid"))
        signature = self.result_document(); signature["protocol_signature"] = "0" * 64
        mutations.append((signature, "result_protocol_signature_mismatch"))
        for operation, reason in (("missing", "result_section_order_mismatch"),
                                  ("additional", "result_section_order_mismatch"),
                                  ("duplicate", "result_section_duplicate"),
                                  ("reordered", "result_section_order_mismatch")):
            damaged = self.result_document()
            if operation == "missing": damaged["sections"].pop()
            elif operation == "additional": damaged["sections"].append(
                {"section_id": "other", "output_name": "other", "cases": []})
            elif operation == "duplicate": damaged["sections"][1] = copy.deepcopy(damaged["sections"][0])
            else: damaged["sections"][0], damaged["sections"][1] = damaged["sections"][1], damaged["sections"][0]
            mutations.append((damaged, reason))
        for document, reason in mutations:
            with self.subTest(reason=reason):
                self.assertIn(reason, contract.validate_result_document(document))

    def test_result_rejects_missing_extra_duplicate_unknown_reordered_cases(self):
        for operation, reason in (
            ("missing", "result_case_order_mismatch:standard"),
            ("additional", "result_case_unknown:standard.extra"),
            ("duplicate", "result_case_duplicate:standard.random64"),
            ("unknown", "result_case_unknown:standard.unknown"),
            ("reordered", "result_case_order_mismatch:standard")):
            damaged = self.result_document(); cases = damaged["sections"][0]["cases"]
            if operation == "missing": cases.pop()
            elif operation == "additional":
                row = copy.deepcopy(cases[-1]); row["case_id"] = "standard.extra"; cases.append(row)
            elif operation == "duplicate": cases[1] = copy.deepcopy(cases[0])
            elif operation == "unknown": cases[0]["case_id"] = "standard.unknown"
            else: cases[0], cases[1] = cases[1], cases[0]
            with self.subTest(operation=operation):
                self.assertIn(reason, contract.validate_result_document(damaged))

    def test_result_rejects_input_seed_generator_and_hash_damage(self):
        cases = []
        seed = self.result_document(); seed["sections"][0]["cases"][0]["inputs"][0]["seed"] += 1
        cases.append((seed, "result_input_seed_mismatch:standard.random64"))
        generator = self.result_document(); generator["sections"][0]["cases"][0]["inputs"][0]["generator"] = "wrong"
        cases.append((generator, "result_input_generator_mismatch:standard.random64"))
        digest = self.result_document(); digest["sections"][0]["cases"][0]["inputs"][0]["sha256"]["A"] = "bad"
        cases.append((digest, "result_input_hash_invalid:standard.random64:A"))
        digits = self.result_document(); digits["sections"][0]["cases"][4]["inputs"][0]["sha256"]["A"] = "d" * 64
        cases.append((digits, "result_digits_design_hash_mismatch"))
        for document, reason in cases:
            self.assertIn(reason, contract.validate_result_document(document))

    def test_result_rejects_partial_or_reordered_input_seeds(self):
        for operation in ("partial", "reordered"):
            damaged = self.result_document()
            rank = next(s for s in damaged["sections"] if s["section_id"] == "rank")
            inputs = rank["cases"][0]["inputs"]
            if operation == "partial": inputs.pop()
            else: inputs[0], inputs[1] = inputs[1], inputs[0]
            self.assertIn("result_input_seed_order_mismatch:rank.eps_1e-08",
                          contract.validate_result_document(damaged))

    def test_result_recomputes_timing_fields(self):
        for field, value, reason in (
            ("raw", None, "result_timing_raw_invalid:standard.random64:router"),
            ("repetitions", 10, "result_timing_repetitions_mismatch:standard.random64:router"),
            ("median", 999, "result_timing_median_mismatch:standard.random64:router"),
            ("mad", 999, "result_timing_mad_mismatch:standard.random64:router")):
            damaged = self.result_document()
            timing = damaged["sections"][0]["cases"][0]["timings"][0]
            if value is None: timing.pop(field)
            else: timing[field] = value
            self.assertIn(reason, contract.validate_result_document(damaged))

    def test_result_recomputes_ratio_direction_value_and_aggregate(self):
        wrong = self.result_document(); case = wrong["sections"][0]["cases"][0]
        case["ratios"] = [{"name": "sequential_reference_over_router",
                           "direction": "router/sequential_reference", "value": .5}]
        self.assertIn("result_ratio_direction_mismatch:standard.random64",
                      contract.validate_result_document(wrong))
        wrong = self.result_document(); case = wrong["sections"][0]["cases"][0]
        case["ratios"] = [{"name": "sequential_reference_over_router",
                           "direction": "sequential_reference/router", "value": 999.0}]
        self.assertIn("result_ratio_value_mismatch:standard.random64",
                      contract.validate_result_document(wrong))
        wrong = self.result_document(); section = wrong["sections"][0]
        section["summary"].update({"ratio_count": 9, "ratio_geomean": 999.0})
        self.assertIn("result_summary_ratio_aggregate_mismatch:standard",
                      contract.validate_result_document(wrong))

    def test_numerical_contract_status_rank_interval_fail_closed(self):
        false = self.result_document(); row = false["sections"][0]["cases"][0]
        row["numerical_contract"] = {"expected": {"status": "unique", "rank": 64},
                                     "actual": {"status": "infinite", "rank": 63},
                                     "valid": False, "reasons": ["wrong_status"]}
        self.assertIn("result_numerical_contract_invalid:standard.random64",
                      contract.validate_result_document(false))
        interval = self.result_document(); diag = interval["sections"][0]["cases"][0]["diagnostics"]
        diag.update({"rank": 64, "rank_lo": 65, "rank_hi": 63})
        self.assertIn("result_rank_interval_invalid:standard.random64",
                      contract.validate_result_document(interval))
        wrong = self.result_document(); row = wrong["sections"][0]["cases"][0]
        row["numerical_contract"]["actual"]["status"] = "infinite"
        row["diagnostics"]["status"] = "infinite"
        self.assertIn("result_numerical_outcome_mismatch:standard.random64",
                      contract.validate_result_document(wrong))

    def test_structural_count_and_unavailable_transition_residual(self):
        structural = self.result_document()
        section = next(s for s in structural["sections"] if s["section_id"] == "structural")
        section["cases"][0]["numerical_contract"]["valid"] = False
        self.assertIn("result_structural_hard_failure_count_mismatch",
                      contract.validate_result_document(structural))
        transition = self.result_document()
        section = next(s for s in transition["sections"] if s["section_id"] == "rank")
        section["cases"][0]["diagnostics"].update(
            {"finite_residual_count": 0, "router_relres": 0.0})
        self.assertIn("result_transition_unavailable_residual_not_null",
                      contract.validate_result_document(transition))

    def test_timing_range_miss_is_observational(self):
        result = self.result_document()
        result["sections"][0]["cases"][0]["observations"]["timing_range"] = "outside-reference-range"
        self.assertEqual(contract.validate_result_document(result), [])


class MetadataValidationTests(ContractTestCase):
    def test_valid_metadata_passes(self):
        self.assertEqual(contract.validate_metadata_document(
            self.metadata_document(), result_bytes=b"{}"), [])

    def test_source_identity_dirty_and_drift_are_rejected(self):
        for path, value, reason in (
            (("before", "git_sha"), "short", "source_before_sha_invalid"),
            (("after", "git_tree_sha"), "z" * 40, "source_after_tree_invalid"),
            (("before", "git_dirty"), True, "source_before_dirty"),
            (("after", "git_sha"), "3" * 40, "source_state_changed")):
            metadata = self.metadata_document(); metadata["source"][path[0]][path[1]] = value
            self.assertIn(reason, contract.validate_metadata_document(metadata, result_bytes=b"{}"))

    def test_result_schema_hash_command_and_dependency_identity_are_required(self):
        for path, value, reason in (
            (("schema_version",), 1, "metadata_schema_version_invalid"),
            (("result", "sha256"), None, "result_hash_mismatch"),
            (("result", "schema_version"), 1, "metadata_result_schema_mismatch"),
            (("result", "protocol_signature"), "0" * 64, "metadata_protocol_signature_mismatch"),
            (("command", "executable_basename"), None, "command_executable_missing"),
            (("dependency_locks",), [], "dependency_lock_identity_incomplete")):
            metadata = self.metadata_document(); cursor = metadata
            for part in path[:-1]: cursor = cursor[part]
            cursor[path[-1]] = value
            self.assertIn(reason, contract.validate_metadata_document(metadata, result_bytes=b"{}"))

    def test_build_and_router_identity_is_fail_closed(self):
        for path, value, reason in (
            (("build", "manifest_sha256"), None, "build_manifest_hash_invalid"),
            (("build", "source", "git_sha"), "4" * 40, "build_source_sha_mismatch"),
            (("build", "router", "basename"), "other.so", "router_basename_mismatch"),
            (("build", "router", "sha256"), None, "router_hash_invalid"),
            (("build", "build_script", "sha256"), None, "build_script_hash_invalid"),
            (("build", "compiler", "identity"), None, "compiler_identity_missing"),
            (("build", "compiler", "command_argv"), [], "compiler_argv_missing"),
            (("build", "linked_blas", "sha256"), None, "linked_blas_hash_invalid")):
            metadata = self.metadata_document(); cursor = metadata
            for part in path[:-1]: cursor = cursor[part]
            cursor[path[-1]] = value
            self.assertIn(reason, contract.validate_metadata_document(metadata, result_bytes=b"{}"))

    def test_runtime_blas_and_thread_controls_are_fail_closed(self):
        metadata = self.metadata_document(); metadata["runtime"]["blas_pools"] = []
        self.assertIn("runtime_blas_pool_missing",
                      contract.validate_metadata_document(metadata, result_bytes=b"{}"))
        metadata = self.metadata_document(); metadata["runtime"]["blas_pools"][0]["num_threads"] = 2
        self.assertIn("runtime_blas_not_single_threaded:libblas.so",
                      contract.validate_metadata_document(metadata, result_bytes=b"{}"))
        metadata = self.metadata_document(); metadata["runtime"]["blas_pools"][0]["sha256"] = "a" * 64
        self.assertIn("runtime_linked_blas_hash_mismatch",
                      contract.validate_metadata_document(metadata, result_bytes=b"{}"))
        metadata = self.metadata_document(); metadata["runtime"]["thread_controls"].pop("MKL_NUM_THREADS")
        self.assertIn("thread_control_not_one:MKL_NUM_THREADS",
                      contract.validate_metadata_document(metadata, result_bytes=b"{}"))

    def test_machine_software_and_eligibility_identity_are_required(self):
        metadata = self.metadata_document(); metadata["machine"]["cpu_model"] = None
        self.assertIn("machine_identity_missing:cpu_model",
                      contract.validate_metadata_document(metadata, result_bytes=b"{}"))
        metadata = self.metadata_document(); metadata["software"]["scikit-learn"] = None
        self.assertIn("software_identity_missing:scikit-learn",
                      contract.validate_metadata_document(metadata, result_bytes=b"{}"))
        metadata = self.metadata_document(); metadata["evidence_eligibility"] = {
            "eligible": True, "reasons": ["partial_diagnostic_run"]}
        self.assertIn("metadata_eligibility_inconsistent",
                      contract.validate_metadata_document(metadata, result_bytes=b"{}"))

    def test_private_identifiers_checkout_and_venv_paths_are_rejected(self):
        for mutate in (
            lambda m: m["generator"].update(path="/home/alice/repo/runner.py"),
            lambda m: m["dependency_locks"][0].update(path="/tmp/venv/req.txt"),
            lambda m: m.update(hostname="private-host"),
            lambda m: m["command"]["argv"].append("/home/alice/.venv/bin/python"),
            lambda m: m["machine"].update(serial_number="secret")):
            metadata = self.metadata_document(); mutate(metadata)
            self.assertIn("metadata_private_or_absolute_value",
                          contract.validate_metadata_document(metadata, result_bytes=b"{}"))

    def test_system_compiler_path_is_not_private(self):
        metadata = self.metadata_document()
        metadata["build"]["compiler"]["command_argv"] = ["/usr/bin/gcc", "-O3"]
        self.assertEqual(contract.validate_metadata_document(metadata, result_bytes=b"{}"), [])


class BuildBindingTests(ContractTestCase):
    def setUp(self):
        super().setUp(); self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.libdir = self.root / "lib"; self.libdir.mkdir()
        self.router = self.libdir / "libaffine_bundle_solver.so"; self.router.write_bytes(b"router")
        self.blas = self.libdir / "libblas.so"; self.blas.write_bytes(b"blas")
        self.build_script = self.root / "build.sh"; self.build_script.write_bytes(b"build")
        self.source = {"git_sha": "1" * 40, "git_tree_sha": "2" * 40,
                       "git_dirty": False}
        self.manifest = {
            "schema_version": 1, "built_at_utc": "2026-09-12T00:00:00Z",
            "source": self.source,
            "build_script": {"path": "build.sh", "sha256": sha_file(self.build_script)},
            "compiler": {"command_argv": ["gcc"], "identity": "gcc test"},
            "router": {"compile_argv": ["gcc", "-O3", "-c"],
                       "link_argv": ["gcc", "-shared", str(self.blas)],
                       "arch_flags": "",
                       "library": {"basename": self.router.name,
                                   "resolved_path": str(self.router),
                                   "sha256": sha_file(self.router)}},
            "openblas": {"basename": self.blas.name,
                         "resolved_path": str(self.blas),
                         "sha256": sha_file(self.blas)}}
        self.write_manifest()

    def tearDown(self): self.temp.cleanup()

    def write_manifest(self, value=None):
        (self.libdir / ".abs-build-manifest.json").write_text(
            json.dumps(self.manifest if value is None else value))

    def verify(self):
        return contract.verify_build_manifest(
            router_path=self.router,
            manifest_path=self.libdir / ".abs-build-manifest.json",
            build_script_path=self.build_script, source_state=self.source)

    def test_adjacent_manifest_verifies_exact_router(self):
        verdict = self.verify()
        self.assertTrue(verdict["verified"], verdict["reasons"])
        self.assertEqual(verdict["router_sha256"], sha_file(self.router))

    def test_missing_stale_tampered_or_different_manifest_fails(self):
        path = self.libdir / ".abs-build-manifest.json"; path.unlink()
        self.assertIn("build_manifest_missing", self.verify()["reasons"])
        path.write_text("not json")
        self.assertIn("build_manifest_invalid_json", self.verify()["reasons"])
        for field_path, value, reason in (
            (("source", "git_sha"), "3" * 40, "build_source_sha_mismatch"),
            (("source", "git_tree_sha"), "4" * 40, "build_source_tree_mismatch"),
            (("router", "library", "sha256"), "0" * 64, "router_library_hash_mismatch"),
            (("router", "library", "basename"), "other.so", "router_library_basename_mismatch"),
            (("router", "library", "resolved_path"), str(self.libdir / "other.so"), "router_library_path_mismatch"),
            (("build_script", "sha256"), "0" * 64, "build_script_hash_mismatch"),
            (("compiler", "command_argv"), ["clang"], "router_compile_compiler_mismatch")):
            damaged = copy.deepcopy(self.manifest); cursor = damaged
            for part in field_path[:-1]: cursor = cursor[part]
            cursor[field_path[-1]] = value; self.write_manifest(damaged)
            self.assertIn(reason, self.verify()["reasons"])

    def test_resolver_loads_only_abs_lib_dir_after_verification(self):
        handle = mock.Mock(); loader = mock.Mock(return_value=handle)
        loaded, evidence = contract.resolve_and_load_router(
            root=self.root, lib_dir=self.libdir, source_state=self.source,
            cdll=loader, build_script_path=self.build_script)
        self.assertIs(loaded, handle); self.assertTrue(evidence["verified"])
        self.assertEqual(loader.call_args.args, (str(self.router.resolve()),))
        for symbol in ("bsolve_router_meta_api", "bsolve_seq_api",
                       "bsolve_lapack_api", "bsolve_fg_counters_reset_api",
                       "bsolve_fg_counters_api"):
            self.assertTrue(hasattr(handle, symbol))

    def test_router_resolving_outside_abs_lib_dir_is_rejected(self):
        outside = self.root / "outside.so"; outside.write_bytes(b"router")
        self.router.unlink(); self.router.symlink_to(outside)
        with self.assertRaises(RuntimeError) as raised:
            contract.resolve_and_load_router(
                root=self.root, lib_dir=self.libdir, source_state=self.source,
                cdll=mock.Mock(), build_script_path=self.build_script)
        self.assertIn("build_manifest_not_adjacent", str(raised.exception))


class PackageTests(ContractTestCase):
    def write_package(self, root, result=None, metadata=None, checksum=True):
        root = Path(root); result = result or self.result_document()
        result_bytes = contract.canonical_json_bytes(result)
        metadata = metadata or self.metadata_document(result_bytes)
        metadata_bytes = contract.canonical_json_bytes(metadata)
        (root / contract.RESULT_FILENAME).write_bytes(result_bytes)
        (root / contract.METADATA_FILENAME).write_bytes(metadata_bytes)
        if checksum:
            (root / contract.CHECKSUM_FILENAME).write_text(
                f"{sha_bytes(result_bytes)}  {contract.RESULT_FILENAME}\n"
                f"{sha_bytes(metadata_bytes)}  {contract.METADATA_FILENAME}\n")

    def test_complete_package_passes_all_four_verdicts(self):
        with tempfile.TemporaryDirectory() as directory:
            self.write_package(directory); report = contract.audit_package(directory)
        self.assertTrue(report["artifact_integrity"]["valid"], report)
        self.assertTrue(report["source_build_runtime_provenance"]["valid"], report)
        self.assertTrue(report["protocol_eligibility"]["eligible"], report)
        self.assertTrue(report["numerical_contract_validity"]["valid"], report)

    def test_missing_wrong_malformed_nonfinite_incomplete_packages_fail(self):
        for damage, reason in (
            ("missing_result", "package_result_missing"),
            ("missing_metadata", "package_metadata_missing"),
            ("missing_checksum", "package_checksum_missing"),
            ("wrong_result", "package_result_checksum_mismatch"),
            ("wrong_metadata", "package_metadata_checksum_mismatch"),
            ("malformed", "package_result_json_invalid"),
            ("nan", "package_result_json_invalid"),
            ("infinity", "package_result_json_invalid")):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory); self.write_package(root)
                if damage == "missing_result": (root / contract.RESULT_FILENAME).unlink()
                elif damage == "missing_metadata": (root / contract.METADATA_FILENAME).unlink()
                elif damage == "missing_checksum": (root / contract.CHECKSUM_FILENAME).unlink()
                elif damage == "wrong_result": (root / contract.RESULT_FILENAME).write_text("{}\n")
                elif damage == "wrong_metadata": (root / contract.METADATA_FILENAME).write_text("{}\n")
                elif damage == "malformed": (root / contract.RESULT_FILENAME).write_text("{")
                elif damage == "nan": (root / contract.RESULT_FILENAME).write_text('{"x":NaN}')
                else: (root / contract.RESULT_FILENAME).write_text('{"x":Infinity}')
                report = contract.audit_package(root)
            self.assertIn(reason, report["artifact_integrity"]["reasons"])

    def test_serialization_failure_preserves_existing_valid_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.write_package(root)
            before = {path.name: path.read_bytes() for path in root.iterdir()}
            bad = self.result_document(); bad["forbidden"] = math.nan
            with self.assertRaises(ValueError):
                contract.publish_package_atomic(
                    result=bad, metadata=self.metadata_document(),
                    result_path=root / contract.RESULT_FILENAME,
                    metadata_path=root / contract.METADATA_FILENAME,
                    checksum_path=root / contract.CHECKSUM_FILENAME)
            after = {path.name: path.read_bytes() for path in root.iterdir()}
        self.assertEqual(after, before)


class RegistryAuditAndCiTests(ContractTestCase):
    def claim(self, claim_id):
        registry = check_paper_claims.load_performance_claim_registry()
        return next(item for item in registry["claims"]
                    if item["claim_id"] == claim_id)

    def test_guard_and_transition_attributions_are_exact(self):
        guard = self.claim("guard.rank1_cost")
        self.assertEqual(guard["generator_dataset"],
                         "numerical suite guard_timing m=10000,n=64,r=1")
        self.assertEqual(guard["machine_protocol_scope"]["protocol"],
                         "3 warmups, 9 timed calls")
        self.assertEqual(guard["evidence_class"], "historical-unconfirmed")
        self.assertEqual(guard["publication_status"], "publication-blocker")
        transition = self.claim("transition.rank_gate")
        self.assertEqual(transition["dimensions_case_identity"],
                         ["512x256; 20 seeds; six epsilon levels"])
        self.assertIsNone(transition["artifact_case_mapping"])
        self.assertNotIn("1500x12", json.dumps(transition))
        self.assertEqual(transition["publication_status"], "publication-blocker")

    def test_claim_counts_exact_blockers_and_two_nonblockers_do_not_change(self):
        registry = check_paper_claims.load_performance_claim_registry()
        report = check_paper_claims.evaluate_performance_claims(registry)
        self.assertEqual(len(registry["claims"]), 20)
        self.assertEqual(set(report["manuscript_publication_readiness"]["reasons"]),
                         EXACT_BLOCKERS)
        self.assertEqual({item["claim_id"] for item in registry["claims"]
                          if item["publication_status"] == "publication-ready"},
                         {"grouped.dgelsy", "scope.tall_directional"})

    def test_legacy_numerical_audit_returns_explicit_failures(self):
        report = check_paper_claims.audit_numerical_suite_package(ROOT / "results")
        reasons = report["artifact_integrity"]["reasons"]
        self.assertFalse(report["artifact_integrity"]["valid"])
        self.assertTrue(any("schema" in reason for reason in reasons), reasons)
        self.assertTrue(any("raw" in reason for reason in reasons), reasons)
        self.assertTrue(any("provenance" in reason for reason in reasons), reasons)

    def test_ci_step_is_gcc_portable_and_nonnumerical(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        marker = "- name: Numerical suite provenance contract"
        self.assertEqual(workflow.count(marker), 1)
        step = workflow.split(marker, 1)[1].split("\n      - name:", 1)[0]
        for required in ("matrix.cc == 'gcc' && matrix.arch_label == 'portable'",
                         "requirements-numerical-suite.txt",
                         "tests/test_numerical_suite_contract.py",
                         "--check-performance-inventory", "-m py_compile"):
            self.assertIn(required, step)
        for forbidden in ("rerun_numerical_suite.py --", "build.sh",
                          "synthetic_bench.py", "pbt_", "upload-artifact"):
            self.assertNotIn(forbidden, step)


class RunnerIntegrationTests(ContractTestCase):
    def setUp(self):
        super().setUp(); self.runner = load_runner_module()
        self.A = np.ascontiguousarray(np.eye(2, dtype=np.float64))
        self.b = np.ascontiguousarray([1.0, 2.0])
        self.x = np.ascontiguousarray([1.0, 2.0])

    def test_load_delegates_abs_lib_dir_and_source(self):
        handle = mock.Mock(); evidence = {"verified": True}
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
                self.runner.contract, "resolve_and_load_router",
                return_value=(handle, evidence)) as resolver:
            loaded = self.runner.load({"git_sha": "1" * 40,
                                       "git_tree_sha": "2" * 40,
                                       "git_dirty": False}, lib_dir=directory)
        self.assertEqual(loaded, (handle, evidence))
        self.assertEqual(Path(resolver.call_args.kwargs["lib_dir"]), Path(directory))

    def test_c_api_rejects_invalid_layout_before_call(self):
        library = mock.Mock()
        with self.assertRaises(ValueError):
            self.runner.router(library, self.A.astype(np.float32), self.b, self.x)
        library.bsolve_router_meta_api.assert_not_called()

    def test_standard_records_raw_input_identity_and_router_berr(self):
        router_out = np.zeros(11); router_out[[0, 2, 3, 4]] = [1, 2, 2, 2]
        router_out[5] = 1e-16; router_out[10] = 2e-16
        seq_out = np.zeros(7); seq_out[[0, 1]] = [1, 2]
        with mock.patch.object(self.runner, "standard_cases",
                               return_value=iter((("random64", (self.A, self.b, self.x)),))), \
                mock.patch.object(self.runner, "med_router", return_value=(
                    2.0, router_out, [float(i) for i in range(1, 12)])), \
                mock.patch.object(self.runner, "med_seq", return_value=(
                    4.0, seq_out, [float(i) for i in range(1, 8)])), \
                contextlib.redirect_stdout(io.StringIO()):
            section = self.runner.run_standard(mock.Mock(), 4)
        row = section["cases"][0]
        self.assertEqual(row["case_id"], "standard.random64")
        self.assertIn("router_berr", row["diagnostics"])
        self.assertNotIn("quality_eta_x", json.dumps(row))
        self.assertEqual(len(row["timings"][0]["raw"]), 11)
        self.assertEqual(len(row["timings"][1]["raw"]), 7)

    def test_guard_records_all_nine_solver_timings(self):
        output = np.zeros(11); output[[0, 2, 3, 4, 7]] = [2, 1, 1, 2, 1.0]
        library = mock.Mock()
        with mock.patch.object(self.runner, "make_integer_rank",
                               return_value=(self.A, self.b, self.x)), \
                mock.patch.object(self.runner, "med_router", return_value=(
                    5.0, output, [float(i) for i in range(1, 10)])), \
                contextlib.redirect_stdout(io.StringIO()):
            section = self.runner.run_guard_timing(library, 4)
        self.assertEqual(len(section["cases"]), 8)
        self.assertTrue(all(len(row["timings"][0]["raw"]) == 9
                            for row in section["cases"]))

    def test_scaling_records_raw_timings_for_exact_thread_schedule(self):
        output = np.zeros(11); output[[0, 2, 3, 4, 7]] = [1, 2, 2, 2, 1.0]
        made = (self.A, self.b, self.x)
        with mock.patch.object(self.runner, "make_grouped", return_value=made), \
                mock.patch.object(self.runner, "make_random", return_value=made), \
                mock.patch.object(self.runner, "med_router", return_value=(
                    2.0, output, [float(i) for i in range(1, 10)])), \
                contextlib.redirect_stdout(io.StringIO()):
            section = self.runner.run_scaling(mock.Mock())
        self.assertEqual([row["observations"]["omp_threads"]
                          for row in section["cases"]], [1] * 3 + [2] * 3 + [4] * 3)
        self.assertTrue(all(len(row["timings"][0]["raw"]) == 9
                            for row in section["cases"]))

    def test_lapack_keeps_separate_end_to_end_raw_timings(self):
        router_output = np.zeros(11)
        router_output[[0, 2, 3, 4, 7]] = [1, 2, 2, 2, 1.0]
        lapack_output = np.zeros(7); lapack_output[[0, 1, 5]] = [1, 2, 1e-16]
        calls = []
        for _ in range(6):
            calls.extend(((2.0, router_output, [float(i) for i in range(1, 8)]),
                          (4.0, lapack_output, [float(i) for i in range(2, 9)])))
        made = (self.A, self.b, self.x)
        with mock.patch.object(self.runner, "make_grouped", return_value=made), \
                mock.patch.object(self.runner, "make_random", return_value=made), \
                mock.patch.object(self.runner, "end2end_ms", side_effect=calls), \
                contextlib.redirect_stdout(io.StringIO()):
            section = self.runner.run_lapack_context(mock.Mock(), 4)
        self.assertEqual(len(section["cases"]), 6)
        for row in section["cases"]:
            self.assertEqual([timing["source"] for timing in row["timings"]],
                             ["perf_counter_ns", "perf_counter_ns"])
            self.assertEqual([len(timing["raw"]) for timing in row["timings"]],
                             [7, 7])

    def test_rank_transition_unavailable_residual_is_null_and_runs_identified(self):
        output = np.zeros(11); output[[0, 2, 3, 4, 7]] = [4, 255, 255, 256, 1.0]
        output[5] = math.nan
        with mock.patch.object(self.runner, "make_rank_transition",
                               return_value=(self.A, self.b, self.x)), \
                mock.patch.object(self.runner, "router", return_value=output), \
                contextlib.redirect_stdout(io.StringIO()):
            section = self.runner.run_rank_transition(mock.Mock(), 4)
        for row in section["cases"]:
            self.assertIsNone(row["diagnostics"]["router_relres"])
            self.assertEqual(row["diagnostics"]["finite_residual_count"], 0)
            self.assertEqual(len(row["timings"][0]["raw"]), 20)
            self.assertTrue(all(run["case_id"] == row["case_id"]
                                for run in row["runs"]))

    def test_structural_records_actual_adjusted_seed(self):
        output = np.zeros(11); output[[0, 2, 3, 4, 7]] = [1, 2, 2, 2, 1.0]
        seen = []
        def fake_router(_library, _A, _b, _x, seed, omp):
            seen.append(seed); return output
        with mock.patch.object(self.runner, "structural_cases", return_value=[
                ("full_n32_x4", self.A, self.b, self.x, "unique", 2)]), \
                mock.patch.object(self.runner, "router", side_effect=fake_router), \
                contextlib.redirect_stdout(io.StringIO()):
            section = self.runner.run_structural(mock.Mock(), 4)
        runs = section["cases"][0]["runs"]
        self.assertEqual([run["seed"] for run in runs], [31001, 31002, 31003])
        self.assertTrue(all(run["case_id"] == "structural.full_n32_x4"
                            for run in runs))

    def test_cli_defaults_diagnostic_and_candidate_is_exact(self):
        diagnostic = self.runner.parse_cli([])
        self.assertEqual(Path(diagnostic.out).name, "numerical_rerun.json")
        self.assertIsNone(diagnostic.metadata_out)
        self.assertIsNone(diagnostic.checksum_out)
        with self.assertRaises(SystemExit):
            self.runner.parse_cli(["--sections", "standard,unknown"])
        with self.assertRaises(SystemExit):
            self.runner.parse_cli(["--candidate", "--reference-machine", "x",
                                   "--sections", "standard,rank"])
        candidate = self.runner.parse_cli([
            "--candidate", "--reference-machine", "x", "--omp", "4",
            "--sections", "standard,rank,guard,scaling,structural,lapack"])
        self.assertEqual((Path(candidate.out).name, Path(candidate.metadata_out).name,
                          Path(candidate.checksum_out).name),
                         ("numerical-suite-reference.json",
                          "numerical-suite-reference.metadata.json",
                          "numerical-suite-reference.sha256"))

    def test_numerical_failure_returns_nonzero(self):
        result = self.result_document(); result["numerical_contract"]["valid"] = False
        self.assertEqual(self.runner.numerical_exit_code(result), 1)
        self.assertEqual(self.runner.numerical_exit_code(self.result_document()), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
