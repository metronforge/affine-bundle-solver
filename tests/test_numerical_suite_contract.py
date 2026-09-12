#!/usr/bin/env python3
"""Fixture-only adversarial tests for numerical-suite evidence contracts."""

from __future__ import annotations

import contextlib
import copy
import ctypes
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

PROTOCOL_FIXTURE = json.loads(
    (ROOT / "tests/fixtures/numerical_suite_protocol_v2.json").read_text())
LITERAL_CASES_BY_ID = {
    item["case_id"]: item for item in PROTOCOL_FIXTURE["cases"]
}
LITERAL_PROTOCOL_SIGNATURE = \
    "b9f774b376c525a111139f0a1c786c4262f88903d064a2860e78795bf57ae1f5"
ROUTER_OPENMP_LIBRARY_SHA256 = "a" * 64
ROUTER_OPENMP_RUNTIME_ID = \
    "ddb64756e2ad9bdb0d4d4c3fa8611a1145b7c34cfb39097c0b9a1e6924a584e4"
UNRELATED_OPENMP_LIBRARY_SHA256 = "b" * 64
UNRELATED_OPENMP_RUNTIME_ID = \
    "80c8aebaaec7a7e7279ab2c52a7de88cc086b962b388f33990c8b7b700d8fdeb"
TEMP_ROUTER_OPENMP_LIBRARY_SHA256 = \
    "325c36ce6dd5eb3ce6ab1750000b0d77b9d4349b29abd9aadf7e7969325adfc8"
TEMP_ROUTER_OPENMP_RUNTIME_ID = \
    "75d3f6973177d20e243fe249cb41431adbf33c5b54b9636a4e0d3a6550439177"

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


class StrictFakeSymbol:
    def __init__(self, name):
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "argtypes", None)
        object.__setattr__(self, "restype", "unset")
        object.__setattr__(self, "calls", [])

    def __call__(self, *args):
        self.calls.append(args)
        if self.name == "bsolve_router_meta_api":
            out = args[-1]
            values = [1.0, 1.0, 2.0, 2.0, 2.0, 1e-16, 1e-16,
                      0.002, 0.0, 1.0, 1e-16]
            for index, value in enumerate(values):
                out[index] = value
        elif self.name in ("bsolve_seq_api", "bsolve_lapack_api"):
            out = args[-1]
            for index, value in enumerate([1.0, 2.0, 0.0, 0.0,
                                           0.003, 1e-16, 1e-16]):
                out[index] = value
        elif self.name == "bsolve_fg_counters_api":
            for index in range(3):
                args[0][index] = 0


class StrictFakeRouterHandle:
    def __init__(self):
        for name in ("bsolve_router_meta_api", "bsolve_seq_api",
                     "bsolve_lapack_api", "bsolve_fg_counters_reset_api",
                     "bsolve_fg_counters_api"):
            setattr(self, name, StrictFakeSymbol(name))


class ContractTestCase(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            contract, "experiments.numerical_suite_contract is not implemented")

    def input_record(self, case_id, seed=None):
        spec = LITERAL_CASES_BY_ID[case_id]
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

    def openmp_identity(self, *, unrelated=False):
        return {
            "runtime_id": (UNRELATED_OPENMP_RUNTIME_ID if unrelated else
                           ROUTER_OPENMP_RUNTIME_ID),
            "basename": "libgomp.so.1", "user_api": "openmp",
            "internal_api": "openmp", "version": None,
            "library_sha256": (UNRELATED_OPENMP_LIBRARY_SHA256 if unrelated
                               else ROUTER_OPENMP_LIBRARY_SHA256),
        }

    def bind_openmp_identity(self, result, metadata, identity=None):
        identity = copy.deepcopy(identity or self.openmp_identity())
        for section in result["sections"]:
            for case in section["cases"]:
                for run in case["runs"]:
                    run["openmp_runtime_identity"] = copy.deepcopy(identity)
        metadata["runtime"]["selected_router_openmp_identity"] = \
            copy.deepcopy(identity)
        metadata["runtime"]["openmp_pools"] = [{
            **copy.deepcopy(identity), "num_threads": 4,
        }]

    def result_case(self, case_id):
        for section in self.result_document()["sections"]:
            for case in section["cases"]:
                if case["case_id"] == case_id:
                    return copy.deepcopy(case)
        raise AssertionError(f"missing fixture case {case_id}")

    def timing(self, spec, offset=1.0):
        raw = [offset + index for index in range(spec["repetitions"])]
        median = float(np.median(raw))
        mad = float(np.median(np.abs(np.asarray(raw) - median)))
        return {
            "operation": spec["operation"], "source": spec["source"],
            "unit": "s", "warmups": spec["warmups"],
            "repetitions": spec["repetitions"], "raw": raw,
            "median": median, "mad": mad,
            "measurement_envelope": spec["measurement_envelope"],
        }

    def decoded_router_diagnostics(self, spec, duration):
        status = spec["expected_status"]
        certainty = ("none" if status in ("fail", "undecidable") else
                     "deterministic" if spec["expected_rank_lo"] ==
                     spec["expected_rank_hi"] else "randomised")
        return {
            "status": status,
            "status_code": {"unique": 1, "infinite": 2,
                            "inconsistent": 3, "fail": 4,
                            "undecidable": 5}[status],
            "certainty": certainty,
            "certainty_code": {"deterministic": 1, "randomised": 2,
                               "none": 3}[certainty],
            "rank": spec["expected_rank"],
            "rank_lo": spec["expected_rank_lo"],
            "rank_hi": spec["expected_rank_hi"],
            "router_relres": (None if status in ("fail", "undecidable")
                              else 1e-16),
            "router_relx": (None if status in
                            ("inconsistent", "fail", "undecidable")
                            else 1e-16),
            "solver_seconds": duration,
            "fallback": False,
            "raw_class": {"unique": 1, "infinite": 2,
                          "inconsistent": 3, "fail": 4,
                          "undecidable": 5}[status],
            "router_berr": (1e-16 if status == "unique" else None),
        }

    def decoded_comparator_diagnostics(self, spec, duration):
        status = spec["expected_status"]
        return {
            "status": status,
            "status_code": {"unique": 1, "infinite": 2,
                            "inconsistent": 3, "fail": 4,
                            "undecidable": 5}[status],
            "rank": spec["expected_rank"],
            "fallback": False,
            "accepted_random": False,
            "solver_seconds": duration,
            "relres": (None if status in ("fail", "undecidable")
                       else 1e-16),
            "relx": (None if status in ("fail", "undecidable")
                     else 1e-16),
        }

    def result_document(self, sections=None):
        rows = []
        chosen = sections or [name for name, _ in EXPECTED_SECTIONS]
        for section_name in chosen:
            cases = []
            for case_id in EXPECTED_CASE_IDS[section_name]:
                spec = LITERAL_CASES_BY_ID[case_id]
                expected = {"status": spec["expected_status"],
                            "rank": spec["expected_rank"]}
                if section_name == "rank":
                    expected["rank_interval"] = [
                        spec["expected_rank_lo"], spec["expected_rank_hi"]]
                timings = [self.timing(item, index + 1.0)
                           for index, item in enumerate(spec["timings"])]
                router_raw = next(item["raw"] for item in timings
                                  if item["operation"] == "router")
                runs = []
                run_contract = spec["run_contract"]
                for index, duration in enumerate(router_raw):
                    status = spec["expected_status"]
                    run_expected = {"status": status,
                                    "rank": spec["expected_rank"]}
                    if section_name == "rank":
                        run_expected["rank_interval"] = [
                            spec["expected_rank_lo"],
                            spec["expected_rank_hi"]]
                    runs.append({
                        "run_id": run_contract["run_id_format"].format(
                            case_id=case_id, repetition_index=index),
                        "case_id": case_id,
                        "generator_seed": run_contract["generator_seeds"][index],
                        "routing_seed": run_contract["routing_seeds"][index],
                        "repetition_index": index,
                        "requested_omp_threads":
                            run_contract["requested_omp_threads"][index],
                        "observed_omp_threads":
                            run_contract["requested_omp_threads"][index],
                        "openmp_runtime_identity": self.openmp_identity(),
                        "duration": {"value": duration, "unit": "s"},
                        "diagnostics": self.decoded_router_diagnostics(
                            spec, duration),
                        "numerical_contract": {
                            "expected": run_expected,
                            "actual": {
                                "status": status,
                                "rank": spec["expected_rank"],
                                **({"rank_interval": [spec["expected_rank_lo"],
                                                       spec["expected_rank_hi"]]}
                                   if section_name == "rank" else {}),
                            },
                            "valid": True, "reasons": [],
                        },
                    })
                comparator_runs = []
                for comparator in spec["comparator_run_contracts"]:
                    raw = next(item["raw"] for item in timings
                               if item["operation"] == comparator["operation"])
                    for index, duration in enumerate(raw):
                        comparator_runs.append({
                            "run_id": comparator["run_id_format"].format(
                                case_id=case_id, repetition_index=index),
                            "case_id": case_id,
                            "operation": comparator["operation"],
                            "repetition_index": index,
                            "duration": {"value": duration, "unit": "s"},
                            "diagnostics": self.decoded_comparator_diagnostics(
                                spec, duration),
                            "numerical_contract": {
                                "expected": {"status": spec["expected_status"],
                                             "rank": spec["expected_rank"]},
                                "actual": {"status": spec["expected_status"],
                                           "rank": spec["expected_rank"]},
                                "valid": True, "reasons": [],
                            },
                        })
                ratios = []
                medians = {item["operation"]: item["median"]
                           for item in timings}
                for required in spec["required_ratios"]:
                    if required["name"] == "one_thread_router_over_router":
                        numerator = medians["router"]
                        denominator = medians["router"]
                    else:
                        numerator = medians[required["numerator_operation"]]
                        denominator = medians[required["denominator_operation"]]
                    ratios.append({**required, "value": numerator / denominator})
                case_diagnostics = self.decoded_router_diagnostics(
                    spec, timings[0]["median"])
                for comparator in spec["comparator_run_contracts"]:
                    operation_runs = [
                        run for run in comparator_runs
                        if run["operation"] == comparator["operation"]]
                    case_diagnostics[comparator["operation"]] = copy.deepcopy(
                        operation_runs[-1]["diagnostics"])
                cases.append({
                    "case_id": case_id,
                    "inputs": [self.input_record(case_id, seed)
                               for seed in spec["input_seeds"]],
                    "timings": timings,
                    "ratios": ratios,
                    "runs": runs,
                    "comparator_runs": comparator_runs,
                    "diagnostics": case_diagnostics,
                    "numerical_contract": {
                        "expected": expected,
                        "actual": {"status": spec["expected_status"],
                                   "rank": spec["expected_rank"],
                                   **({"rank_interval": [
                                       spec["expected_rank_lo"],
                                       spec["expected_rank_hi"]]}
                                      if section_name == "rank" else {})},
                        "valid": True, "reasons": [],
                    },
                    "observations": {"timing_range": "not-evaluated"},
                })
            summary = {"case_count": len(cases)}
            if section_name == "structural":
                router_values = [value for case in cases
                                 for value in case["timings"][0]["raw"]]
                summary.update({
                    "routing_seeds_per_instance": 3,
                    "check_count": 3 * len(cases),
                    "hard_failure_count": 0,
                    "reported_hard_failure_count": 0,
                    "failures": [],
                    "max_consistent_relres": 1e-16,
                    "median_router_seconds": float(np.median(router_values)),
                })
            ratios = [ratio["value"] for case in cases
                      for ratio in case["ratios"]]
            if ratios:
                summary.update({
                    "ratio_name": PROTOCOL_FIXTURE[
                        "section_summary_contracts"][section_name]["ratio_name"],
                    "ratio_count": len(ratios),
                    "ratio_geomean": float(np.exp(np.mean(np.log(ratios)))),
                    "ratio_median": float(np.median(ratios)),
                })
            rows.append({"section_id": section_name,
                         "output_name": dict(EXPECTED_SECTIONS)[section_name],
                         "cases": cases, "summary": summary})
        router_count = sum(len(case["runs"]) for section in rows
                           for case in section["cases"])
        comparator_counts = {
            operation: sum(
                run["operation"] == operation
                for section in rows for case in section["cases"]
                for run in case["comparator_runs"])
            for operation in ("sequential_reference", "dgelsy")
        }
        ratio_count = sum(len(case["ratios"]) for section in rows
                          for case in section["cases"])
        return {
            "schema_version": 2,
            "protocol_id": "affine-bundle-numerical-suite-v2",
            "protocol_signature": LITERAL_PROTOCOL_SIGNATURE,
            "sections": rows,
            "evidence_counts": {
                "router_runs": router_count,
                "sequential_reference_runs":
                    comparator_counts["sequential_reference"],
                "dgelsy_runs": comparator_counts["dgelsy"],
                "ratios": ratio_count,
            },
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
                "protocol_signature": LITERAL_PROTOCOL_SIGNATURE,
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
                "openmp_pools": [{**self.openmp_identity(),
                                  "num_threads": 4}],
                "selected_router_openmp_identity": self.openmp_identity(),
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
        self.assertEqual(contract.PROTOCOL_SIGNATURE,
                         LITERAL_PROTOCOL_SIGNATURE)
        self.assertEqual(PROTOCOL_FIXTURE["protocol_signature"],
                         LITERAL_PROTOCOL_SIGNATURE)

    def test_complete_protocol_matches_independent_literal_fixture(self):
        actual_cases = [
            case
            for section in contract.CANONICAL_PROTOCOL["sections"]
            for case in section["cases"]
        ]
        self.assertEqual(actual_cases, PROTOCOL_FIXTURE["cases"])
        self.assertEqual(
            [[name, output] for name, output in contract.CANONICAL_SECTIONS],
            PROTOCOL_FIXTURE["sections"])
        self.assertEqual(contract.CANONICAL_PROTOCOL["candidate_omp"], 4)
        self.assertEqual(contract.CANONICAL_PROTOCOL["scaling_openmp_schedule"],
                         [1, 2, 4])
        self.assertEqual(contract.CANONICAL_PROTOCOL["execution_contract"],
                         PROTOCOL_FIXTURE["execution_contract"])
        self.assertEqual(contract.CANONICAL_PROTOCOL["evidence_counts"],
                         PROTOCOL_FIXTURE["evidence_counts"])
        self.assertEqual(contract.CANONICAL_PROTOCOL[
            "section_summary_contracts"],
            PROTOCOL_FIXTURE["section_summary_contracts"])

    def test_rank_transition_expectations_are_signed(self):
        first = contract.CANONICAL_CASES_BY_ID["rank.eps_1e-08"]
        last = contract.CANONICAL_CASES_BY_ID["rank.eps_1e-12"]
        self.assertEqual((first["expected_status"], first["expected_rank"],
                          first["expected_rank_lo"], first["expected_rank_hi"]),
                         ("unique", 256, 256, 256))
        self.assertEqual((last["expected_status"], last["expected_rank"],
                          last["expected_rank_lo"], last["expected_rank_hi"]),
                         ("undecidable", 255, 255, 256))

    def test_scaled_structural_generator_identity_names_actual_callable(self):
        scaled = [case for case in PROTOCOL_FIXTURE["cases"]
                  if case["case_id"].startswith("structural.scaled_")]
        self.assertEqual(len(scaled), 4)
        self.assertTrue(all(case["generator"] == "make_structured_rank"
                            for case in scaled))
        self.assertTrue(all(case["generator_parameters"]["args"][-1] is True
                            for case in scaled))

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


class StatusMappingTests(ContractTestCase):
    def setUp(self):
        super().setUp()
        self.runner = load_runner_module()

    def test_fail_is_never_decoded_as_undecidable(self):
        self.assertEqual(self.runner.decode_status(4), "fail")
        self.assertNotEqual(self.runner.decode_status(4), "undecidable")

    def test_undecidable_is_decoded_from_public_value_five(self):
        self.assertEqual(self.runner.decode_status(5), "undecidable")

    def test_unknown_status_fails_closed(self):
        for value in (0, 6, -1, 999, 4.9, True, "4", math.nan, math.inf):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.runner.decode_status(value)

    def test_python_mapping_matches_public_header(self):
        header = (ROOT / "include/affine_bundle/router.h").read_text()
        import re
        header_values = {
            name.lower(): int(value)
            for name, value in re.findall(
                r"ABS_STATUS_(UNIQUE|INFINITE|INCONSISTENT|FAIL|UNDECIDABLE)"
                r"\s*=\s*(\d+)", header)
        }
        self.assertEqual(header_values, {
            "unique": 1, "infinite": 2, "inconsistent": 3,
            "fail": 4, "undecidable": 5,
        })
        self.assertEqual(self.runner.STATUS_CODES,
                         {value: name for name, value in header_values.items()})

    def test_public_output_layout_certainty_and_quality_threshold_are_literal(self):
        import re
        header = (ROOT / "include/affine_bundle/router.h").read_text()
        certainties = {
            name.lower(): int(value)
            for name, value in re.findall(
                r"ABS_CERTAINTY_(DETERMINISTIC|RANDOMISED|NONE)\s*=\s*(\d+)",
                header)
        }
        indices = {
            name.lower(): int(value)
            for name, value in re.findall(
                r"ABS_OUT_(STATUS|CERTAINTY|RANK|RANK_LO|RANK_HI|RELRES|RELX|SECONDS|FALLBACK|CLS|BERR)\s*=\s*(\d+)",
                header)
        }
        threshold = float(re.search(
            r"#define\s+ABS_QUALITY_THRESHOLD\s+([^\s]+)", header).group(1))
        self.assertEqual(certainties, {
            "deterministic": 1, "randomised": 2, "none": 3})
        self.assertEqual(indices, {
            "status": 0, "certainty": 1, "rank": 2, "rank_lo": 3,
            "rank_hi": 4, "relres": 5, "relx": 6, "seconds": 7,
            "fallback": 8, "cls": 9, "berr": 10})
        self.assertEqual(threshold, 1e-14)
        self.assertEqual(self.runner.CERTAINTY_CODES,
                         {1: "deterministic", 2: "randomised", 3: "none"})
        self.assertEqual(self.runner.ROUTER_OUTPUT_INDICES, indices)
        self.assertEqual(self.runner.ABS_QUALITY_THRESHOLD, threshold)

    def test_router_output_decoder_rejects_coercions_and_semantic_damage(self):
        valid = np.asarray([1, 1, 2, 2, 2, 1e-16, 2e-16, 0.003,
                            0, 1, 3e-16], dtype=np.float64)
        decoded = self.runner.decode_router_output(valid)
        self.assertEqual((decoded["status"], decoded["certainty"],
                          decoded["raw_class"], decoded["fallback"]),
                         ("unique", "deterministic", 1, False))
        self.assertEqual(decoded["router_relx"], 2e-16)
        for index, value in ((0, 4.9), (1, 1.2), (2, -1), (3, math.inf),
                             (4, math.nan), (8, 2), (9, 2), (10, math.inf)):
            damaged = valid.copy(); damaged[index] = value
            with self.subTest(index=index, value=value), self.assertRaises(ValueError):
                self.runner.decode_router_output(damaged)

    def test_router_output_decoder_enforces_unavailable_and_berr_semantics(self):
        for status in (4, 5):
            values = np.asarray([status, 3, 0, 0, 0, math.nan, math.nan,
                                 0.003, 0, status, math.nan], dtype=np.float64)
            decoded = self.runner.decode_router_output(values)
            self.assertIsNone(decoded["router_relres"])
            self.assertIsNone(decoded["router_relx"])
            self.assertIsNone(decoded["router_berr"])
            for index in (5, 6, 10):
                damaged = values.copy(); damaged[index] = 0.0
                with self.subTest(status=status, index=index), \
                        self.assertRaises(ValueError):
                    self.runner.decode_router_output(damaged)
        for certainty, berr in ((1, 1.1e-14), (2, 1e-16)):
            values = np.asarray([1, certainty, 2, 2, 2, 1e-16, 1e-16,
                                 0.003, 0, 1, berr], dtype=np.float64)
            with self.subTest(certainty=certainty), self.assertRaises(ValueError):
                self.runner.decode_router_output(values)

    def test_comparator_decoder_is_exact_and_status_aware(self):
        valid = np.asarray([2, 1, 0, 0, 0.004, 1e-16, 1e-16])
        decoded = self.runner.decode_comparator_output(valid)
        self.assertEqual((decoded["status"], decoded["rank"],
                          decoded["fallback"], decoded["accepted_random"]),
                         ("infinite", 1, False, False))
        for index, value in ((0, 2.5), (1, -1), (2, 0.2), (3, 2),
                             (4, math.inf), (5, -1), (6, math.inf)):
            damaged = valid.copy(); damaged[index] = value
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.runner.decode_comparator_output(damaged)

    def test_comparator_inconsistent_preserves_finite_reference_error(self):
        values = np.asarray([3, 63, 0, 0, 0.004, 0.25, 0.75])
        decoded = self.runner.decode_comparator_output(values)
        self.assertEqual(decoded["status"], "inconsistent")
        self.assertEqual(decoded["relres"], 0.25)
        self.assertEqual(decoded["relx"], 0.75)

    def test_router_certainty_rank_intervals_match_producer(self):
        valid = (
            [1, 1, 2, 2, 2, 1e-16, 1e-16, 0.003, 0, 1, 1e-16],
            [2, 1, 0, 0, 0, 1e-16, 1e-16, 0.003, 0, 2, math.nan],
            [3, 1, 1, 1, 1, 0.25, math.nan, 0.003, 0, 3, math.nan],
            [2, 2, 1, 1, 2, 1e-16, 1e-16, 0.003, 0, 2, math.nan],
            [5, 3, 0, 0, 2, math.nan, math.nan, 0.003, 1, 5, math.nan],
            [5, 3, 1, 0, 2, math.nan, math.nan, 0.003, 1, 5, math.nan],
            [4, 3, 0, 0, 0, math.nan, math.nan, 0.003, 1, 4, math.nan],
        )
        for values in valid:
            with self.subTest(status=values[0], certainty=values[1]):
                try:
                    decoded = self.runner.decode_router_output(
                        np.asarray(values, dtype=np.float64), max_rank=2)
                except TypeError as exc:
                    self.fail(f"rank-bound decoding unavailable: {exc}")
                self.assertEqual(decoded["status_code"], values[0])
        invalid = (
            [2, 1, 1, 1, 2, 1e-16, 1e-16, 0.003, 0, 2, math.nan],
            [2, 2, 1, 1, 1, 1e-16, 1e-16, 0.003, 0, 2, math.nan],
            [4, 3, 0, 0, 1, math.nan, math.nan, 0.003, 1, 4, math.nan],
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.runner.decode_router_output(
                    np.asarray(values, dtype=np.float64), max_rank=2)

    def test_router_deterministic_widened_interval_is_rejected(self):
        widened = np.asarray(
            [2, 1, 1, 1, 2, 1e-16, 1e-16, 0.003, 0, 2, math.nan])
        with self.assertRaises(ValueError):
            self.runner.decode_router_output(widened)

    def test_all_protocol_statuses_are_representable(self):
        expected = {case["expected_status"]
                    for case in PROTOCOL_FIXTURE["cases"]}
        self.assertEqual(expected,
                         {"unique", "infinite", "inconsistent", "undecidable"})
        self.assertTrue(expected <= set(self.runner.STATUS_CODES.values()))


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
        envelope = self.result_document()
        envelope["sections"][0]["cases"][0]["timings"][0][
            "measurement_envelope"] = "includes_runtime_discovery"
        self.assertIn(
            "result_timing_envelope_mismatch:standard.random64:router",
            contract.validate_result_document(envelope))

    def test_every_required_run_identity_and_seed_sequence_is_mandatory(self):
        mutations = []
        missing = self.result_document(); missing["sections"][0]["cases"][0]["runs"].pop(4)
        mutations.append((missing, "result_run_shape_mismatch:standard.random64"))
        extra = self.result_document(); extra_run = copy.deepcopy(
            extra["sections"][0]["cases"][0]["runs"][-1])
        extra_run["run_id"] += ".extra"; extra_run["repetition_index"] = 11
        extra["sections"][0]["cases"][0]["runs"].append(extra_run)
        mutations.append((extra, "result_run_shape_mismatch:standard.random64"))
        duplicate = self.result_document(); duplicate["sections"][0]["cases"][0]["runs"][1] = copy.deepcopy(
            duplicate["sections"][0]["cases"][0]["runs"][0])
        mutations.append((duplicate, "result_run_identity_duplicate:standard.random64"))
        reordered = self.result_document(); runs = reordered["sections"][0]["cases"][0]["runs"]
        runs[0], runs[1] = runs[1], runs[0]
        mutations.append((reordered, "result_run_order_mismatch:standard.random64"))
        wrong_seed = self.result_document(); wrong_seed["sections"][0]["cases"][0]["runs"][2]["routing_seed"] += 1
        mutations.append((wrong_seed, "result_run_routing_seed_mismatch:standard.random64"))
        wrong_generator = self.result_document(); wrong_generator["sections"][0]["cases"][0]["runs"][2]["generator_seed"] += 1
        mutations.append((wrong_generator, "result_run_generator_seed_mismatch:standard.random64"))
        for document, reason in mutations:
            with self.subTest(reason=reason):
                self.assertIn(reason, contract.validate_result_document(document))

    def test_run_duration_unit_and_timing_raw_must_agree(self):
        wrong_unit = self.result_document()
        wrong_unit["sections"][0]["cases"][0]["runs"][0]["duration"]["unit"] = "ms"
        self.assertIn("result_run_duration_unit_mismatch:standard.random64",
                      contract.validate_result_document(wrong_unit))
        wrong_timing_unit = self.result_document()
        wrong_timing_unit["sections"][0]["cases"][0]["timings"][0]["unit"] = "seconds"
        self.assertIn("result_timing_unit_mismatch:standard.random64:router",
                      contract.validate_result_document(wrong_timing_unit))
        bad_duration = self.result_document()
        bad_duration["sections"][0]["cases"][0]["runs"][0]["duration"]["value"] = 0.0
        self.assertIn("result_run_duration_invalid:standard.random64",
                      contract.validate_result_document(bad_duration))
        hidden = self.result_document()
        hidden["sections"][0]["cases"][0]["runs"][3]["duration"]["value"] = 999.0
        self.assertIn("result_run_timing_disagreement:standard.random64",
                      contract.validate_result_document(hidden))

    def test_every_comparator_run_and_raw_duration_is_mandatory(self):
        mutations = []
        missing = self.result_document()
        missing["sections"][0]["cases"][0]["comparator_runs"].pop(3)
        mutations.append((missing,
                          "result_comparator_run_shape_mismatch:standard.random64:sequential_reference"))
        duplicate = self.result_document()
        runs = duplicate["sections"][0]["cases"][0]["comparator_runs"]
        runs[1] = copy.deepcopy(runs[0])
        mutations.append((duplicate,
                          "result_comparator_run_identity_duplicate:standard.random64:sequential_reference"))
        reordered = self.result_document()
        runs = reordered["sections"][0]["cases"][0]["comparator_runs"]
        runs[0], runs[1] = runs[1], runs[0]
        mutations.append((reordered,
                          "result_comparator_run_order_mismatch:standard.random64:sequential_reference"))
        hidden = self.result_document()
        hidden["sections"][0]["cases"][0]["comparator_runs"][2][
            "duration"]["value"] = 99.0
        mutations.append((hidden,
                          "result_comparator_timing_disagreement:standard.random64:sequential_reference"))
        for document, reason in mutations:
            with self.subTest(reason=reason):
                self.assertIn(reason, contract.validate_result_document(document))

    def test_failed_comparator_run_invalidates_case_and_ratio(self):
        damaged = self.result_document()
        row = damaged["sections"][0]["cases"][0]
        failed = row["comparator_runs"][3]
        failed["diagnostics"].update({"status": "fail", "status_code": 4,
                                      "rank": 0, "relres": None,
                                      "relx": None})
        failed["numerical_contract"] = {
            "expected": {"status": "unique", "rank": 64},
            "actual": {"status": "fail", "rank": 0},
            "valid": False, "reasons": ["status_mismatch"],
        }
        self.assertIn(
            "result_comparator_run_numerical_contract_invalid:standard.random64:sequential_reference",
            contract.validate_result_document(damaged))
        self.assertIn("result_ratio_comparator_invalid:standard.random64",
                      contract.validate_result_document(damaged))
        self.assertIn("result_case_run_aggregate_mismatch:standard.random64",
                      contract.validate_result_document(damaged))

    def test_comparator_diagnostics_are_exact_and_expected(self):
        for field, value in (("rank", 63), ("status", "infinite"),
                             ("solver_seconds", math.inf),
                             ("relres", math.inf)):
            damaged = self.result_document()
            run = damaged["sections"][0]["cases"][0]["comparator_runs"][0]
            run["diagnostics"][field] = value
            self.assertIn(
                "result_comparator_run_diagnostics_invalid:standard.random64:sequential_reference",
                contract.validate_result_document(damaged))
        damaged = self.result_document()
        damaged["sections"][0]["cases"][0]["diagnostics"][
            "sequential_reference"]["rank"] = 63
        self.assertIn(
            "result_case_comparator_diagnostics_mismatch:standard.random64:sequential_reference",
            contract.validate_result_document(damaged))

    def test_required_ratio_shape_is_exact(self):
        missing = self.result_document(); missing["sections"][0]["cases"][0]["ratios"] = []
        self.assertIn("result_ratio_shape_mismatch:standard.random64",
                      contract.validate_result_document(missing))
        duplicate = self.result_document(); ratios = duplicate["sections"][0]["cases"][0]["ratios"]
        ratios.append(copy.deepcopy(ratios[0]))
        self.assertIn("result_ratio_identity_duplicate:standard.random64",
                      contract.validate_result_document(duplicate))
        unexpected = self.result_document(); rank = next(
            section for section in unexpected["sections"] if section["section_id"] == "rank")
        rank["cases"][0]["ratios"] = [{
            "ratio_id": "unexpected", "name": "dgelsy_over_router",
            "direction": "dgelsy/router", "numerator_operation": "dgelsy",
            "denominator_operation": "router", "value": 1.0,
        }]
        self.assertIn("result_ratio_shape_mismatch:rank.eps_1e-08",
                      contract.validate_result_document(unexpected))

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

    def test_section_summary_shape_and_all_aggregates_are_exact(self):
        for mutate, reason in (
            (lambda summary: summary.pop("ratio_median"),
             "result_summary_shape_mismatch:standard"),
            (lambda summary: summary.update(extra=1),
             "result_summary_shape_mismatch:standard"),
            (lambda summary: summary.update(ratio_name="router_over_reference"),
             "result_summary_ratio_name_mismatch:standard"),
            (lambda summary: summary.update(ratio_median=999.0),
             "result_summary_ratio_aggregate_mismatch:standard")):
            damaged = self.result_document()
            mutate(damaged["sections"][0]["summary"])
            self.assertIn(reason, contract.validate_result_document(damaged))
        inappropriate = self.result_document()
        rank = next(section for section in inappropriate["sections"]
                    if section["section_id"] == "rank")
        rank["summary"]["ratio_count"] = 0
        self.assertIn("result_summary_shape_mismatch:rank",
                      contract.validate_result_document(inappropriate))

    def test_top_level_contract_and_evidence_totals_are_exact(self):
        for contract_value in (
                {"valid": True},
                {"valid": True, "reasons": [], "extra": True},
                {"valid": False, "reasons": ["hidden"]}):
            damaged = self.result_document()
            damaged["numerical_contract"] = contract_value
            self.assertIn("result_numerical_contract_invalid",
                          contract.validate_result_document(damaged))
        damaged = self.result_document()
        damaged["evidence_counts"]["dgelsy_runs"] += 1
        self.assertIn("result_evidence_counts_mismatch",
                      contract.validate_result_document(damaged))

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

    def test_one_failed_intermediate_run_cannot_be_hidden(self):
        damaged = self.result_document()
        row = damaged["sections"][0]["cases"][0]
        failed = row["runs"][4]
        failed["diagnostics"].update({"status": "fail", "rank": 0,
                                      "rank_lo": 0, "rank_hi": 0})
        failed["numerical_contract"] = {
            "expected": {"status": "unique", "rank": 64},
            "actual": {"status": "fail", "rank": 0},
            "valid": False, "reasons": ["status_mismatch"],
        }
        self.assertIn("result_run_numerical_contract_invalid:standard.random64",
                      contract.validate_result_document(damaged))
        self.assertIn("result_case_run_aggregate_mismatch:standard.random64",
                      contract.validate_result_document(damaged))
        self.assertIn("result_numerical_contract_aggregate_mismatch",
                      contract.validate_result_document(damaged))

    def test_run_case_diagnostic_and_rank_transition_interval_must_agree(self):
        damaged = self.result_document(); row = damaged["sections"][0]["cases"][0]
        row["diagnostics"]["rank"] = 63
        self.assertIn("result_case_run_diagnostics_mismatch:standard.random64",
                      contract.validate_result_document(damaged))
        transition = self.result_document(); rank = next(
            section for section in transition["sections"] if section["section_id"] == "rank")
        rank["cases"][3]["runs"][6]["diagnostics"]["rank_hi"] = 255
        self.assertIn("result_run_rank_interval_mismatch:rank.eps_3e-10",
                      contract.validate_result_document(transition))
        transition = self.result_document(); rank = next(
            section for section in transition["sections"]
            if section["section_id"] == "rank")
        rank["cases"][3]["numerical_contract"]["actual"]["rank_interval"] = [
            255, 255]
        self.assertIn(
            "result_numerical_actual_interval_mismatch:rank.eps_3e-10",
            contract.validate_result_document(transition))

    def test_structural_count_and_unavailable_transition_residual(self):
        structural = self.result_document()
        section = next(s for s in structural["sections"] if s["section_id"] == "structural")
        section["cases"][0]["numerical_contract"]["valid"] = False
        section["cases"][0]["runs"][0]["numerical_contract"].update(
            valid=False, reasons=["status_mismatch"])
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

    def test_inconsistent_sequential_reference_keeps_finite_relx(self):
        result = self.result_document()
        case = result["sections"][0]["cases"][3]
        self.assertEqual(case["case_id"], "standard.inconsistent64")
        for run in case["comparator_runs"]:
            run["diagnostics"]["relx"] = 0.75
        case["diagnostics"]["sequential_reference"]["relx"] = 0.75
        self.assertEqual(contract.validate_result_document(result), [])

    def test_solver_reported_run_duration_is_bound_to_diagnostics(self):
        for operation in ("router", "sequential_reference"):
            result = self.result_document()
            section = result["sections"][0]
            case = section["cases"][0]
            runs = (case["runs"] if operation == "router" else
                    case["comparator_runs"])
            for run in runs:
                run["duration"]["value"] *= 10.0
            timing = next(item for item in case["timings"]
                          if item["operation"] == operation)
            timing["raw"] = [run["duration"]["value"] for run in runs]
            timing["median"] = float(np.median(timing["raw"]))
            timing["mad"] = float(np.median(
                np.abs(np.asarray(timing["raw"]) - timing["median"])))
            medians = {item["operation"]: item["median"]
                       for item in case["timings"]}
            case["ratios"][0]["value"] = (
                medians["sequential_reference"] / medians["router"])
            ratios = [ratio["value"] for row in section["cases"]
                      for ratio in row["ratios"]]
            section["summary"]["ratio_geomean"] = float(
                np.exp(np.mean(np.log(ratios))))
            section["summary"]["ratio_median"] = float(np.median(ratios))
            reason = ("result_run_solver_duration_mismatch:standard.random64"
                      if operation == "router" else
                      "result_comparator_solver_duration_mismatch:"
                      "standard.random64:sequential_reference")
            with self.subTest(operation=operation):
                self.assertIn(reason, contract.validate_result_document(result))

    def test_result_openmp_identity_requires_hash_and_canonical_runtime_id(self):
        result = self.result_document()
        metadata = self.metadata_document(contract.canonical_json_bytes(result))
        self.bind_openmp_identity(result, metadata)
        self.assertEqual(contract.validate_result_document(result), [])
        for field, value in (("library_sha256", None),
                             ("library_sha256", "bad"),
                             ("runtime_id", "not-the-canonical-id")):
            damaged = copy.deepcopy(result)
            identity = damaged["sections"][0]["cases"][0]["runs"][0][
                "openmp_runtime_identity"]
            if value is None:
                identity.pop(field)
            else:
                identity[field] = value
            with self.subTest(field=field, value=value):
                self.assertIn(
                    "result_run_openmp_identity_invalid:standard.random64",
                    contract.validate_result_document(damaged))
        for value in ("missing", "", True, 3, [], {}):
            damaged = copy.deepcopy(result)
            identity = damaged["sections"][0]["cases"][0]["runs"][0][
                "openmp_runtime_identity"]
            if value == "missing":
                identity.pop("version")
            else:
                identity["version"] = value
            with self.subTest(version=value):
                self.assertIn(
                    "result_run_openmp_identity_invalid:standard.random64",
                    contract.validate_result_document(damaged))

    def test_artifact_rejects_deterministic_widened_rank_interval(self):
        result = self.result_document()
        run = result["sections"][0]["cases"][0]["runs"][0]
        run["diagnostics"]["rank_hi"] += 1
        self.assertIn(
            "result_run_diagnostics_invalid:standard.random64",
            contract.validate_result_document(result))

    def test_boolean_integer_fields_never_satisfy_result_schema(self):
        mutations = (
            (lambda d: d.update(schema_version=True),
             "result_schema_version_invalid"),
            (lambda d: d["sections"][0]["cases"][0]["inputs"][0].update(
                seed=True), "result_input_seed_mismatch:standard.random64"),
            (lambda d: d["sections"][0]["cases"][0]["inputs"][0].update(
                m=True), "result_input_shape_mismatch:standard.random64"),
            (lambda d: d["sections"][0]["cases"][0]["runs"][0][
                "diagnostics"].update(status_code=True),
             "result_run_diagnostics_invalid:standard.random64"),
            (lambda d: d["sections"][0]["cases"][0]["runs"][0][
                "diagnostics"].update(certainty_code=True),
             "result_run_diagnostics_invalid:standard.random64"),
            (lambda d: d["sections"][0]["cases"][0]["runs"][0][
                "diagnostics"].update(raw_class=True),
             "result_run_diagnostics_invalid:standard.random64"),
            (lambda d: d["sections"][0]["cases"][0]["runs"][1].update(
                repetition_index=True),
             "result_run_repetition_index_mismatch:standard.random64"),
            (lambda d: next(s for s in d["sections"]
                            if s["section_id"] == "rank")["cases"][0][
                                "timings"][0].update(warmups=False),
             "result_timing_warmups_mismatch:rank.eps_1e-08:router"),
            (lambda d: d["sections"][0]["cases"][0]["timings"][0].update(
                repetitions=True),
             "result_timing_repetitions_mismatch:standard.random64:router"),
            (lambda d: d["sections"][0]["summary"].update(case_count=True),
             "result_summary_case_count_mismatch:standard"),
            (lambda d: d["evidence_counts"].update(router_runs=True),
             "result_evidence_counts_mismatch"),
            (lambda d: next(s for s in d["sections"]
                            if s["section_id"] == "structural")[
                                "summary"].update(hard_failure_count=False),
             "result_summary_integer_invalid:structural:hard_failure_count"),
        )
        for mutate, reason in mutations:
            result = self.result_document(); mutate(result)
            with self.subTest(reason=reason):
                self.assertIn(reason, contract.validate_result_document(result))


class MetadataValidationTests(ContractTestCase):
    def test_valid_metadata_passes(self):
        self.assertEqual(contract.validate_metadata_document(
            self.metadata_document(), result_bytes=b"{}"), [])

    def test_nullable_openmp_version_is_valid_but_malformed_versions_fail(self):
        result = self.result_document()
        result_bytes = contract.canonical_json_bytes(result)
        metadata = self.metadata_document(result_bytes)
        self.bind_openmp_identity(result, metadata)
        self.assertEqual(contract.validate_result_document(result), [])
        self.assertEqual(contract.validate_metadata_document(
            metadata, result_bytes=result_bytes), [])
        for target, reason in (
                ("selected_router_openmp_identity",
                 "runtime_router_openmp_identity_invalid"),
                ("openmp_pools", "runtime_openmp_pool_identity_incomplete")):
            for value in ("", True, 3, [], {}):
                damaged = copy.deepcopy(metadata)
                identity = (damaged["runtime"][target] if target !=
                            "openmp_pools" else damaged["runtime"][target][0])
                identity["version"] = value
                with self.subTest(target=target, value=value):
                    self.assertIn(reason, contract.validate_metadata_document(
                        damaged, result_bytes=result_bytes))
            missing = copy.deepcopy(metadata)
            identity = (missing["runtime"][target] if target !=
                        "openmp_pools" else missing["runtime"][target][0])
            identity.pop("version")
            with self.subTest(target=target, value="missing"):
                self.assertIn(reason, contract.validate_metadata_document(
                    missing, result_bytes=result_bytes))

    def test_openmp_identity_hash_disambiguates_same_named_runtimes(self):
        result = self.result_document()
        result_bytes = contract.canonical_json_bytes(result)
        metadata = self.metadata_document(result_bytes)
        selected = self.openmp_identity()
        self.bind_openmp_identity(result, metadata, selected)
        metadata["runtime"]["openmp_pools"].insert(0, {
            **self.openmp_identity(unrelated=True), "num_threads": 8,
        })
        verdict = contract.evaluate_eligibility(
            result=result, metadata=metadata, candidate=True, omp=4)
        self.assertEqual(verdict["reasons"], [])
        damaged = copy.deepcopy(metadata)
        damaged["runtime"]["selected_router_openmp_identity"] = \
            self.openmp_identity(unrelated=True)
        verdict = contract.evaluate_eligibility(
            result=result, metadata=damaged, candidate=True, omp=4)
        self.assertIn("result_metadata_router_openmp_identity_mismatch",
                      verdict["reasons"])

    def test_openmp_identity_rejects_missing_or_malformed_library_hash(self):
        result = self.result_document()
        result_bytes = contract.canonical_json_bytes(result)
        metadata = self.metadata_document(result_bytes)
        self.bind_openmp_identity(result, metadata)
        for target in ("selected", "pool"):
            for value in (None, "bad"):
                damaged = copy.deepcopy(metadata)
                identity = (damaged["runtime"][
                    "selected_router_openmp_identity"] if target == "selected"
                    else damaged["runtime"]["openmp_pools"][0])
                if value is None:
                    identity.pop("library_sha256")
                else:
                    identity["library_sha256"] = value
                with self.subTest(target=target, value=value):
                    self.assertIn(
                        "runtime_router_openmp_identity_invalid" if
                        target == "selected" else
                        "runtime_openmp_pool_identity_incomplete",
                        contract.validate_metadata_document(
                            damaged, result_bytes=result_bytes))

    def test_boolean_integer_fields_never_satisfy_metadata_schema(self):
        mutations = (
            (lambda m: m.update(schema_version=True),
             "metadata_schema_version_invalid"),
            (lambda m: m["result"].update(schema_version=True),
             "metadata_result_schema_mismatch"),
            (lambda m: m["build"].update(manifest_schema_version=True),
             "build_manifest_schema_invalid"),
            (lambda m: m["runtime"]["blas_pools"][0].update(
                num_threads=True), "runtime_blas_pool_identity_incomplete"),
            (lambda m: m["runtime"]["openmp_pools"][0].update(
                num_threads=True), "runtime_openmp_pool_identity_incomplete"),
            (lambda m: m["machine"].update(physical_cores=True),
             "machine_identity_invalid:physical_cores"),
        )
        for mutate, reason in mutations:
            metadata = self.metadata_document(); mutate(metadata)
            with self.subTest(reason=reason):
                self.assertIn(reason, contract.validate_metadata_document(
                    metadata, result_bytes=b"{}"))

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

    def test_mixed_blas_and_openmp_pools_are_classified_by_user_api(self):
        pools = [
            {"user_api": "blas", "internal_api": "openblas",
             "num_threads": 1, "version": "0.3-test",
             "basename": "libopenblas.so", "sha256": "9" * 64},
            {"user_api": "openmp", "internal_api": "openmp",
             "num_threads": 4, "version": None,
             "basename": "libgomp.so.1",
             "library_sha256": ROUTER_OPENMP_LIBRARY_SHA256},
        ]
        split = contract.partition_threadpools(pools)
        self.assertEqual([item["basename"] for item in split["blas_pools"]],
                         ["libopenblas.so"])
        self.assertEqual(split["blas_pools"][0]["num_threads"], 1)
        self.assertEqual([item["basename"] for item in split["openmp_pools"]],
                         ["libgomp.so.1"])
        self.assertEqual(split["openmp_pools"][0]["num_threads"], 4)
        metadata = self.metadata_document()
        metadata["runtime"].update(split)
        metadata["build"]["linked_blas"]["basename"] = "libopenblas.so"
        metadata["runtime"]["blas_pools"][0]["sha256"] = "9" * 64
        self.assertNotIn("runtime_blas_not_single_threaded:libgomp.so.1",
                         contract.validate_metadata_document(
                             metadata, result_bytes=b"{}"))

    def test_router_openmp_identity_is_mandatory_and_cross_bound_to_runs(self):
        metadata = self.metadata_document()
        metadata["runtime"].pop("selected_router_openmp_identity")
        self.assertIn("runtime_router_openmp_identity_missing",
                      contract.validate_metadata_document(
                          metadata, result_bytes=b"{}"))
        result = self.result_document()
        metadata = self.metadata_document(contract.canonical_json_bytes(result))
        metadata["runtime"]["selected_router_openmp_identity"][
            "runtime_id"] = "unrelated|openmp|runtime"
        verdict = contract.evaluate_eligibility(
            result=result, metadata=metadata, candidate=True, omp=4)
        self.assertIn("result_metadata_router_openmp_identity_mismatch",
                      verdict["reasons"])

    def test_unrelated_openmp_pool_remains_recorded_without_invalidating_router(self):
        metadata = self.metadata_document()
        metadata["runtime"]["openmp_pools"].insert(
            0, {**self.openmp_identity(unrelated=True), "num_threads": 8})
        self.assertEqual(contract.validate_metadata_document(
            metadata, result_bytes=b"{}"), [])

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

    def test_duplicate_json_keys_fail_closed_at_every_nesting_level(self):
        duplicate_documents = (
            ("result", b'{"schema_version":2,"schema_version":2}',
             "package_result_json_duplicate_key"),
            ("result", b'{"runs":[{"diagnostics":{"rank":1,"rank":1}}]}',
             "package_result_json_duplicate_key"),
            ("metadata", b'{"schema_version":2,"schema_version":2}',
             "package_metadata_json_duplicate_key"),
            ("metadata", b'{"runtime":{"openmp_pools":[],"openmp_pools":[]}}',
             "package_metadata_json_duplicate_key"),
            ("metadata", b'{"build":{"router":{},"router":{}}}',
             "package_metadata_json_duplicate_key"),
        )
        for target, payload, reason in duplicate_documents:
            with self.subTest(target=target, payload=payload), \
                    tempfile.TemporaryDirectory() as directory:
                root = Path(directory); self.write_package(root)
                result_path = root / contract.RESULT_FILENAME
                metadata_path = root / contract.METADATA_FILENAME
                if target == "result":
                    result_path.write_bytes(payload)
                else:
                    metadata_path.write_bytes(payload)
                result_bytes = result_path.read_bytes()
                metadata_bytes = metadata_path.read_bytes()
                (root / contract.CHECKSUM_FILENAME).write_text(
                    f"{sha_bytes(result_bytes)}  {contract.RESULT_FILENAME}\n"
                    f"{sha_bytes(metadata_bytes)}  {contract.METADATA_FILENAME}\n")
                report = contract.audit_package(root)
            self.assertIn(reason, report["artifact_integrity"]["reasons"])
        self.assertEqual(contract.strict_json_loads(
            '{"left":{"rank":1},"right":{"rank":1}}'),
            {"left": {"rank": 1}, "right": {"rank": 1}})


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
                         "--check-performance-inventory", "-m py_compile",
                         "line.strip().split('==', 1)"):
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

    @contextlib.contextmanager
    def observed_openmp(self, _library, requested, *, strict):
        yield {
            "valid": True, "reasons": [],
            "requested_num_threads": requested,
            "observed_num_threads": requested,
            "runtime_identity": self.openmp_identity(),
        }

    def main_hooks(self, sections, *, observed_threads=4):
        handle = StrictFakeRouterHandle()
        contract._configure_router_handle(handle)
        published = []

        @contextlib.contextmanager
        def runtime_context(_library, requested, *, strict):
            observation = {
                "valid": requested == observed_threads,
                "reasons": ([] if requested == observed_threads else
                            ["openmp_requested_observed_mismatch"]),
                "requested_num_threads": requested,
                "observed_num_threads": observed_threads,
                "runtime_identity": self.openmp_identity(),
            }
            if strict and not observation["valid"]:
                raise RuntimeError("openmp_requested_observed_mismatch")
            yield observation

        def execute_sections(library, args):
            # This is the only numerical boundary exercised: one tiny 2x2 call.
            with runtime_context(library, 4, strict=args.candidate) as observation:
                output = self.runner.router(
                    library, self.A, self.b, self.x, seed=877)
            self.assertEqual(output["status"], "unique")
            self.assertEqual(observation["observed_num_threads"], observed_threads)
            return copy.deepcopy(sections)

        state = {"git_sha": "1" * 40, "git_tree_sha": "2" * 40,
                 "git_dirty": False}
        runtime = copy.deepcopy(self.metadata_document()["runtime"])
        build = {"verified": True, "router_sha256": "8" * 64,
                 "manifest_sha256": "6" * 64}

        def metadata(**kwargs):
            return self.metadata_document(
                contract.canonical_json_bytes(kwargs["result"]))

        hooks = {
            "source_state": lambda: copy.deepcopy(state),
            "load": lambda _state: (handle, copy.deepcopy(build)),
            "execute_sections": execute_sections,
            "runtime_info": lambda _build: copy.deepcopy(runtime),
            "reverify": lambda evidence, _after: evidence,
            "metadata": metadata,
            "publish": lambda **kwargs: published.append(kwargs),
            "atomic_json": lambda *_args, **_kwargs: None,
            "utc_now": lambda: "2026-09-12T12:00:00Z",
            "monotonic": lambda: 10.0,
            "blas_context": contextlib.nullcontext,
        }
        return hooks, published, handle

    def candidate_argv(self, directory):
        root = Path(directory)
        return ["--candidate", "--reference-machine", "fixture-machine",
                "--sections", "standard,rank,guard,scaling,structural,lapack",
                "--out", str(root / contract.RESULT_FILENAME),
                "--metadata-out", str(root / contract.METADATA_FILENAME),
                "--checksum-out", str(root / contract.CHECKSUM_FILENAME)]

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

    def test_router_handle_uses_exact_public_ctypes_signatures(self):
        handle = StrictFakeRouterHandle()
        contract._configure_router_handle(handle)
        pointer = ctypes.POINTER(ctypes.c_double)
        self.assertEqual(handle.bsolve_router_meta_api.argtypes, [
            pointer, pointer, pointer, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulonglong,
            ctypes.c_int, pointer])
        self.assertIsNone(handle.bsolve_router_meta_api.restype)
        self.assertEqual(handle.bsolve_seq_api.argtypes,
                         [pointer, pointer, pointer, ctypes.c_int,
                          ctypes.c_int, pointer])
        self.assertIsNone(handle.bsolve_seq_api.restype)
        self.assertEqual(handle.bsolve_lapack_api.argtypes,
                         [pointer, pointer, pointer, ctypes.c_int,
                          ctypes.c_int, pointer])
        self.assertIsNone(handle.bsolve_lapack_api.restype)
        self.assertEqual(handle.bsolve_fg_counters_reset_api.argtypes, [])
        self.assertIsNone(handle.bsolve_fg_counters_reset_api.restype)
        self.assertEqual(handle.bsolve_fg_counters_api.argtypes,
                         [ctypes.POINTER(ctypes.c_ulonglong)])
        self.assertIsNone(handle.bsolve_fg_counters_api.restype)

    def test_openmp_control_and_observation_are_outside_timed_calls(self):
        events = []

        @contextlib.contextmanager
        def runtime_context(_library, requested, *, strict):
            events.extend(("runtime_identified", "control_entered",
                           "threads_observed"))
            yield {
                "valid": True, "reasons": [],
                "requested_num_threads": requested,
                "observed_num_threads": requested,
                "runtime_identity": self.openmp_identity(),
            }
            events.append("control_torn_down")

        class Clock:
            def __init__(self):
                values = []
                for index in range(7):
                    values.extend((index * 100_000_000,
                                   index * 100_000_000 + (index + 1) * 1_000_000))
                self.values = iter(values)
            def __call__(self):
                events.append("timer")
                return next(self.values)

        handle = StrictFakeRouterHandle()
        original = handle.bsolve_router_meta_api

        def logged_call(*args):
            events.append("router_call")
            original(*args)
        logged_call.argtypes = original.argtypes
        logged_call.restype = original.restype
        handle.bsolve_router_meta_api = logged_call
        median, _last, raw, _runs = self.runner.med_router(
            handle, self.A, self.b, self.x, case_id="lapack.random64",
            generator_seed=101, omp=4, warm=2, reps=7,
            warmup_seeds=[47001, 47001], source="perf_counter_ns",
            candidate=True, runtime_context=runtime_context, clock_ns=Clock())
        first_timer = events.index("timer")
        last_timer = len(events) - 1 - events[::-1].index("timer")
        self.assertLess(events.index("threads_observed"), first_timer)
        self.assertGreater(events.index("control_torn_down"), last_timer)
        self.assertEqual(raw, [0.001, 0.002, 0.003, 0.004,
                               0.005, 0.006, 0.007])
        self.assertEqual(median, 0.004)
        ratio = self.runner._ratio("lapack.random64", 0.020, median)
        self.assertEqual(ratio["direction"], "dgelsy/router")
        self.assertEqual(ratio["value"], 5.0)

    def test_comparator_runs_preserve_every_timed_result(self):
        outputs = []
        for index in range(7):
            status = 4 if index == 3 else 1
            outputs.append([status, 64 if status == 1 else 0, 0, 0,
                            0.01 + index, (1e-16 if status == 1 else math.nan),
                            (1e-16 if status == 1 else math.nan)])

        class Symbol:
            def __call__(self, *_args):
                out = _args[-1]
                for index, value in enumerate(outputs.pop(0)):
                    out[index] = value

        handle = type("Handle", (), {"bsolve_seq_api": Symbol()})()
        median, last, raw, runs = self.runner.med_seq(
            handle, self.A, self.b, self.x,
            case_id="standard.random64", warm=0, reps=7)
        self.assertEqual(len(runs), 7)
        self.assertEqual([run["repetition_index"] for run in runs],
                         list(range(7)))
        self.assertEqual([run["duration"]["value"] for run in runs], raw)
        self.assertFalse(runs[3]["numerical_contract"]["valid"])
        self.assertEqual(last["status"], "unique")
        self.assertEqual(median, 3.01)

    def test_inconsistent_sequential_warmup_accepts_finite_relx(self):
        class Symbol:
            def __init__(self):
                self.calls = 0
            def __call__(self, *_args):
                self.calls += 1
                out = _args[-1]
                for index, value in enumerate(
                        [3, 64, 0, 0, 0.003, 0.25, 0.75]):
                    out[index] = value

        symbol = Symbol()
        handle = type("Handle", (), {"bsolve_seq_api": symbol})()
        median, last, raw, runs = self.runner.med_seq(
            handle, self.A, self.b, self.x,
            case_id="standard.inconsistent64", warm=2, reps=7)
        self.assertEqual(symbol.calls, 9)
        self.assertEqual(median, 0.003)
        self.assertEqual(last["relx"], 0.75)
        self.assertEqual([run["diagnostics"]["relx"] for run in runs],
                         [0.75] * 7)
        self.assertEqual(raw, [0.003] * 7)

    def fake_controller_factory(self, pools, events=None, *, mismatch=False):
        events = [] if events is None else events

        class Limit:
            def __init__(self, selected, requested):
                self.selected = selected; self.requested = requested
                self.previous = [pool["num_threads"] for pool in selected]
            def __enter__(self):
                events.append(("limit_enter", self.requested))
                for pool in self.selected:
                    pool["num_threads"] = (self.requested + 1 if mismatch
                                           else self.requested)
                return self
            def __exit__(self, *_args):
                events.append(("limit_exit", self.requested))
                for pool, previous in zip(self.selected, self.previous):
                    pool["num_threads"] = previous
                return False

        class Controller:
            def __init__(self, selected=None):
                self.selected = pools if selected is None else selected
            def info(self):
                events.append(("info", tuple(
                    pool.get("filepath") for pool in self.selected)))
                return [dict(pool) for pool in self.selected]
            def select(self, **kwargs):
                filepath = kwargs["filepath"]
                selected = [pool for pool in self.selected
                            if pool.get("filepath") == filepath]
                events.append(("select", filepath, len(selected)))
                return Controller(selected)
            def limit(self, *, limits, user_api):
                self.assert_user_api = user_api
                return Limit(self.selected, limits)

        return Controller

    def mixed_runtime_pools(self):
        return [
            {"user_api": "openmp", "internal_api": "openmp",
             "num_threads": 8, "version": None,
             "prefix": "libgomp-sklearn",
             "filepath": "/venv/sklearn.libs/libgomp-vendored.so"},
            {"user_api": "blas", "internal_api": "openblas",
             "num_threads": 1, "version": "0.3-test",
             "prefix": "libopenblas",
             "filepath": "/venv/numpy.libs/libopenblas.so"},
            {"user_api": "openmp", "internal_api": "openmp",
             "num_threads": 8, "version": None,
             "prefix": "libgomp",
             "filepath": "/usr/lib/libgomp.so.1"},
        ]

    def test_router_openmp_runtime_is_selected_among_unrelated_runtimes(self):
        events = []; pools = self.mixed_runtime_pools()
        controller = self.fake_controller_factory(pools, events)
        with self.runner.openmp_runtime_context(
                object(), 4, strict=True,
                owner_resolver=lambda _library: "/usr/lib/libgomp.so.1",
                controller_factory=controller,
                library_hasher=lambda _path: ROUTER_OPENMP_LIBRARY_SHA256) \
                as observation:
            self.assertTrue(observation["valid"])
            self.assertEqual(observation["observed_num_threads"], 4)
            self.assertEqual(observation["runtime_identity"]["basename"],
                             "libgomp.so.1")
            self.assertEqual(pools[0]["num_threads"], 8)
        self.assertIn(("select", "/usr/lib/libgomp.so.1", 1), events)
        self.assertEqual(pools[0]["num_threads"], 8)

    def test_nullable_openmp_version_is_accepted_by_live_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner_dir = root / "system"; owner_dir.mkdir()
            unrelated_dir = root / "sklearn.libs"; unrelated_dir.mkdir()
            owner = owner_dir / "libgomp.so.1"
            unrelated = unrelated_dir / "libgomp.so.1"
            owner.write_bytes(b"router-openmp")
            unrelated.write_bytes(b"vendored-openmp")
            pools = [
                {"user_api": "blas", "internal_api": "openblas",
                 "num_threads": 1, "version": "0.3-test",
                 "filepath": str(root / "libopenblas.so")},
                {"user_api": "openmp", "internal_api": "openmp",
                 "num_threads": 8, "version": None,
                 "filepath": str(unrelated)},
                {"user_api": "openmp", "internal_api": "openmp",
                 "num_threads": 8, "version": None,
                 "filepath": str(owner)},
            ]
            controller = self.fake_controller_factory(pools)
            try:
                with self.runner.openmp_runtime_context(
                        object(), 4, strict=True,
                        owner_resolver=lambda _library: str(owner),
                        controller_factory=controller) as observation:
                    self.assertTrue(observation["valid"])
                    identity = observation["runtime_identity"]
                    self.assertIsNone(identity["version"])
                    self.assertEqual(identity["library_sha256"],
                                     TEMP_ROUTER_OPENMP_LIBRARY_SHA256)
                    self.assertEqual(identity["runtime_id"],
                                     TEMP_ROUTER_OPENMP_RUNTIME_ID)
                    self.assertNotIn(str(owner), json.dumps(identity))
                    self.assertNotIn(str(unrelated), json.dumps(identity))
            except RuntimeError as exc:
                self.fail(f"nullable router OpenMP runtime rejected: {exc}")

    def test_same_named_openmp_runtimes_are_disambiguated_by_owner_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owner_dir = root / "system"; owner_dir.mkdir()
            unrelated_dir = root / "sklearn.libs"; unrelated_dir.mkdir()
            owner = owner_dir / "libgomp.so.1"
            unrelated = unrelated_dir / "libgomp.so.1"
            owner.write_bytes(b"router-openmp")
            unrelated.write_bytes(b"vendored-openmp")
            pools = [
                {"user_api": "openmp", "internal_api": "openmp",
                 "num_threads": 8, "version": None,
                 "filepath": str(unrelated)},
                {"user_api": "openmp", "internal_api": "openmp",
                 "num_threads": 8, "version": None,
                 "filepath": str(owner)},
            ]
            controller = self.fake_controller_factory(pools)
            try:
                with self.runner.openmp_runtime_context(
                        object(), 4, strict=True,
                        owner_resolver=lambda _library: str(owner),
                        controller_factory=controller) as observation:
                    identity = observation["runtime_identity"]
                    self.assertEqual(identity["library_sha256"],
                                     TEMP_ROUTER_OPENMP_LIBRARY_SHA256)
                    self.assertNotEqual(identity["library_sha256"],
                                        sha_file(unrelated))
            except RuntimeError as exc:
                self.fail(f"hashed owner selection rejected: {exc}")

    def test_router_openmp_symbol_owner_resolution_is_injectable(self):
        callback_type = ctypes.CFUNCTYPE(ctypes.c_int)
        symbol = callback_type(lambda: 4)

        class Dladdr:
            def __call__(self, _address, info):
                info._obj.filename = b"/usr/lib/libgomp.so.1"
                return 1

        process = type("Process", (), {"dladdr": Dladdr()})()
        library = type("Library", (), {"omp_get_max_threads": symbol})()
        owner = self.runner.resolve_router_openmp_owner(
            library, dlopen=lambda _name: process)
        self.assertEqual(owner, "/usr/lib/libgomp.so.1")

    def test_router_openmp_runtime_failures_are_closed(self):
        base = self.mixed_runtime_pools()
        cases = (
            (lambda _library: None, base, False,
             "openmp_router_runtime_unidentified"),
            (lambda _library: "/missing/libomp.so", base, False,
             "openmp_router_runtime_pool_missing"),
            (lambda _library: "/usr/lib/libgomp.so.1",
             base + [dict(base[-1])], False,
             "openmp_router_runtime_pool_ambiguous"),
            (lambda _library: "/usr/lib/libgomp.so.1", base, True,
             "openmp_requested_observed_mismatch"),
        )
        for resolver, pools, mismatch, reason in cases:
            controller = self.fake_controller_factory(pools, mismatch=mismatch)
            with self.subTest(reason=reason), self.assertRaisesRegex(
                    RuntimeError, reason):
                with self.runner.openmp_runtime_context(
                        object(), 4, strict=True, owner_resolver=resolver,
                        controller_factory=controller,
                        library_hasher=lambda _path:
                            ROUTER_OPENMP_LIBRARY_SHA256):
                    pass

    def test_router_openmp_runtime_drift_is_closed(self):
        pools = self.mixed_runtime_pools()
        controller = self.fake_controller_factory(pools)
        owners = iter(("/usr/lib/libgomp.so.1",
                       "/venv/sklearn.libs/libgomp-vendored.so"))
        with self.assertRaisesRegex(RuntimeError,
                                    "openmp_router_runtime_changed"):
            with self.runner.openmp_runtime_context(
                    object(), 4, strict=True,
                    owner_resolver=lambda _library: next(owners),
                    controller_factory=controller,
                    library_hasher=lambda _path:
                        ROUTER_OPENMP_LIBRARY_SHA256):
                pass

    def test_main_candidate_success_uses_only_injected_tiny_boundaries(self):
        result = self.result_document()
        hooks, published, handle = self.main_hooks(result["sections"])
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(self.runner.ctypes, "CDLL",
                                  side_effect=AssertionError("real CDLL reached")), \
                mock.patch.object(self.runner, "standard_cases",
                                  side_effect=AssertionError("generator reached")), \
                contextlib.redirect_stdout(io.StringIO()):
            code = self.runner.main(self.candidate_argv(directory), hooks=hooks)
        self.assertEqual(code, 0)
        self.assertEqual(len(published), 1)
        self.assertEqual(len(handle.bsolve_router_meta_api.calls), 1)

    def test_main_candidate_rejects_intermediate_failure_and_missing_ratio(self):
        for damage in ("intermediate", "missing_ratio"):
            result = self.result_document()
            row = result["sections"][0]["cases"][0]
            if damage == "intermediate":
                row["runs"][4]["numerical_contract"].update(
                    valid=False, reasons=["status_mismatch"])
                row["numerical_contract"].update(
                    valid=False, reasons=["run_failed"])
            else:
                row["ratios"] = []
            hooks, published, _handle = self.main_hooks(result["sections"])
            with self.subTest(damage=damage), tempfile.TemporaryDirectory() as directory, \
                    self.assertRaises(RuntimeError), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.runner.main(self.candidate_argv(directory), hooks=hooks)
            self.assertEqual(published, [])

    def test_main_candidate_openmp_mismatch_fails_before_publication(self):
        result = self.result_document()
        hooks, published, _handle = self.main_hooks(
            result["sections"], observed_threads=2)
        with tempfile.TemporaryDirectory() as directory, \
                self.assertRaisesRegex(RuntimeError,
                                       "openmp_requested_observed_mismatch"), \
                contextlib.redirect_stdout(io.StringIO()):
            self.runner.main(self.candidate_argv(directory), hooks=hooks)
        self.assertEqual(published, [])

    def test_main_diagnostic_continues_where_candidate_fails_closed(self):
        result = self.result_document(); row = result["sections"][0]["cases"][0]
        row["runs"][4]["numerical_contract"].update(
            valid=False, reasons=["status_mismatch"])
        row["numerical_contract"].update(valid=False, reasons=["run_failed"])
        hooks, published, _handle = self.main_hooks(result["sections"])
        with tempfile.TemporaryDirectory() as directory, \
                contextlib.redirect_stdout(io.StringIO()):
            code = self.runner.main([
                "--sections", "standard,rank,guard,scaling,structural,lapack",
                "--out", str(Path(directory) / "diagnostic.json")], hooks=hooks)
        self.assertEqual(code, 1)
        self.assertEqual(published, [])

    def test_standard_records_raw_input_identity_and_router_berr(self):
        case = self.result_case("standard.random64")
        router_out = case["runs"][-1]["diagnostics"]
        seq_out = case["comparator_runs"][-1]["diagnostics"]
        with mock.patch.object(self.runner, "standard_cases",
                               return_value=iter((("random64", (self.A, self.b, self.x), 101),))), \
                mock.patch.object(self.runner, "med_router", return_value=(
                    2.0, router_out, [float(i) for i in range(1, 12)],
                    case["runs"])), \
                mock.patch.object(self.runner, "med_seq", return_value=(
                    4.0, seq_out, [float(i) for i in range(1, 8)],
                    case["comparator_runs"])), \
                contextlib.redirect_stdout(io.StringIO()):
            section = self.runner.run_standard(mock.Mock(), 4)
        row = section["cases"][0]
        self.assertEqual(row["case_id"], "standard.random64")
        self.assertIn("router_berr", row["diagnostics"])
        self.assertNotIn("quality_eta_x", json.dumps(row))
        self.assertEqual(len(row["timings"][0]["raw"]), 11)
        self.assertEqual(len(row["timings"][1]["raw"]), 7)

    def test_standard_generator_uses_the_same_seed_it_records(self):
        made = (self.A, self.b, self.x)
        seen = []
        spec = contract.CANONICAL_CASES_BY_ID["standard.random64"]
        old_seed = spec["input_seeds"][0]
        try:
            spec["input_seeds"][0] = 909

            def random_generator(m, n, rank, seed):
                seen.append((m, n, rank, seed)); return made

            with mock.patch.object(self.runner, "make_random",
                                   side_effect=random_generator), \
                    mock.patch.object(self.runner, "make_grouped",
                                      return_value=made), \
                    mock.patch.object(self.runner, "make_digits",
                                      return_value=made):
                first_name, _arrays, actual_seed = next(
                    self.runner.standard_cases())
            self.assertEqual(first_name, "random64")
            self.assertEqual(actual_seed, 909)
            self.assertEqual(seen[0][-1], actual_seed)
        finally:
            spec["input_seeds"][0] = old_seed

    def test_guard_records_all_nine_solver_timings(self):
        output = np.zeros(11); output[[0, 2, 3, 4, 7]] = [2, 1, 1, 2, 1.0]
        library = mock.Mock()
        with mock.patch.object(self.runner, "make_integer_rank",
                               return_value=(self.A, self.b, self.x)), \
                mock.patch.object(self.runner, "med_router", side_effect=lambda *_args, **kwargs: (
                    5.0, output, [float(i) for i in range(1, 10)],
                    self.result_case(kwargs["case_id"])["runs"])), \
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
                mock.patch.object(self.runner, "med_router", side_effect=lambda *_args, **kwargs: (
                    2.0, output, [float(i) for i in range(1, 10)],
                    self.result_case(kwargs["case_id"])["runs"])), \
                contextlib.redirect_stdout(io.StringIO()):
            section = self.runner.run_scaling(mock.Mock())
        self.assertEqual([row["observations"]["omp_threads"]
                          for row in section["cases"]], [1] * 3 + [2] * 3 + [4] * 3)
        self.assertTrue(all(len(row["timings"][0]["raw"]) == 9
                            for row in section["cases"]))

    def test_lapack_keeps_separate_end_to_end_raw_timings(self):
        made = (self.A, self.b, self.x)
        cases = {name: self.result_case(f"lapack.{name}") for name in (
            "random64", "grouped64", "rankdef64", "random128",
            "rankdef256", "random512")}
        with mock.patch.object(self.runner, "make_grouped", return_value=made), \
                mock.patch.object(self.runner, "make_random", return_value=made), \
                mock.patch.object(self.runner, "med_router", side_effect=lambda *_args, **kwargs: (
                    2.0, cases[kwargs["case_id"].removeprefix("lapack.")]["runs"][-1]["diagnostics"],
                    [float(i) for i in range(1, 8)],
                    cases[kwargs["case_id"].removeprefix("lapack.")]["runs"])), \
                mock.patch.object(self.runner, "end2end_seconds", side_effect=lambda *_args, **kwargs: (
                    4.0, cases[kwargs["case_id"].removeprefix("lapack.")]["comparator_runs"][-1]["diagnostics"],
                    [float(i) for i in range(2, 9)],
                    cases[kwargs["case_id"].removeprefix("lapack.")]["comparator_runs"])), \
                contextlib.redirect_stdout(io.StringIO()):
            section = self.runner.run_lapack_context(mock.Mock(), 4)
        self.assertEqual(len(section["cases"]), 6)
        for row in section["cases"]:
            self.assertEqual([timing["source"] for timing in row["timings"]],
                             ["perf_counter_ns", "perf_counter_ns"])
            self.assertEqual([len(timing["raw"]) for timing in row["timings"]],
                             [7, 7])

    def test_rank_transition_unavailable_residual_is_null_and_runs_identified(self):
        spec = LITERAL_CASES_BY_ID["rank.eps_1e-12"]
        output = self.decoded_router_diagnostics(spec, 1.0)
        with mock.patch.object(self.runner, "make_rank_transition",
                               return_value=(self.A, self.b, self.x)), \
                mock.patch.object(self.runner, "router", return_value=output), \
                mock.patch.object(self.runner, "openmp_runtime_context",
                                  self.observed_openmp), \
                contextlib.redirect_stdout(io.StringIO()):
            section = self.runner.run_rank_transition(mock.Mock(), 4)
        for row in section["cases"]:
            self.assertIsNone(row["diagnostics"]["router_relres"])
            self.assertEqual(row["diagnostics"]["finite_residual_count"], 0)
            self.assertEqual(len(row["timings"][0]["raw"]), 20)
            self.assertTrue(all(run["case_id"] == row["case_id"]
                                for run in row["runs"]))

    def test_structural_records_actual_adjusted_seed(self):
        spec = LITERAL_CASES_BY_ID["structural.full_n32_x4"]
        output = self.decoded_router_diagnostics(spec, 1.0)
        seen = []
        def fake_router(_library, _A, _b, _x, seed):
            seen.append(seed); return output
        with mock.patch.object(self.runner, "structural_cases", return_value=[
                ("full_n32_x4", self.A, self.b, self.x, "unique", 32, 20036)]), \
                mock.patch.object(self.runner, "router", side_effect=fake_router), \
                mock.patch.object(self.runner, "openmp_runtime_context",
                                  self.observed_openmp), \
                contextlib.redirect_stdout(io.StringIO()):
            section = self.runner.run_structural(mock.Mock(), 4)
        runs = section["cases"][0]["runs"]
        self.assertEqual([run["routing_seed"] for run in runs],
                         [31001, 31002, 31003])
        self.assertTrue(all(run["generator_seed"] == 20036 for run in runs))
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
