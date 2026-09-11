#!/usr/bin/env python3
"""Focused contract tests for the portable synthetic benchmark harness."""

import copy
import hashlib
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments import synthetic_bench as bench


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def complete_rows(repeats=11):
    return [
        {
            "schema_version": 2,
            "case_id": case_id,
            "family": case_id.split(".", 1)[0],
            "m": m,
            "n": n,
            "baseline_kind": baseline_kind,
            "numerical_valid": True,
            "router_timings_s": [1.0] * repeats,
            "baseline_timings_s": [2.0] * repeats,
            "router_s": 1.0,
            "baseline_s": 2.0,
            "ratio_direction": "baseline_over_router",
            "baseline_over_router": 2.0,
        }
        for case_id, m, n, baseline_kind in bench.CANONICAL_REFERENCE_SIGNATURE
    ]


def eligibility_inputs(**overrides):
    values = {
        "args": SimpleNamespace(
            seed=20260909, repeats=11, driver="gelsy", scale=1.0,
            no_large=False, reference_machine="reference-host"),
        "rows": complete_rows(),
        "source_state": {
            "git_sha": "a" * 40,
            "git_tree_sha": "b" * 40,
            "git_dirty": False,
        },
        "machine": {
            "cpu_model": "CPU", "physical_cores": 4,
            "logical_cores": 8, "ram_bytes": 1024,
            "smt_enabled": True, "os": "Linux", "os_version": "test-os",
            "kernel": "test-kernel",
        },
        "software": {"python": "3", "numpy": "2", "scipy": "1"},
        "thread_control": {
            "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1",
        },
        "threadpools": [
            {"user_api": "blas", "internal_api": "openblas",
             "num_threads": 1, "version": "1"}
        ],
        "build_verification": {
            "verified": True, "reasons": [],
            "manifest": {"schema_version": 1},
        },
    }
    values.update(overrides)
    return values


class LsmrValidationTests(unittest.TestCase):
    def setUp(self):
        self.A = np.eye(2)
        self.b = np.array([1.0, -2.0])

    def result(self, *, x=None, istop=1, itn=1, normr=0.0,
               normar=0.0, norma=1.0, conda=1.0, normx=math.sqrt(5.0)):
        return (self.b.copy() if x is None else np.asarray(x, dtype=float),
                istop, itn, normr, normar, norma, conda, normx)

    def test_rejects_least_squares_termination_for_compatible_system(self):
        self.assertEqual(bench.LSMR_ACCEPTED_ISTOP, frozenset((0, 1, 4)))
        self.assertEqual(bench.LSMR_RELATIVE_RESIDUAL_TOLERANCE, 1e-10)
        for istop in (2, 3, 5, 6):
            with self.subTest(istop=istop):
                verdict = bench.validate_lsmr_result(
                    self.result(istop=istop), self.A, self.b, maxiter=2)
                self.assertFalse(verdict["valid"])
                self.assertIn(f"istop={istop}", verdict["reason"])

    def test_rejects_iteration_limit_without_convergence(self):
        verdict = bench.validate_lsmr_result(
            self.result(istop=7, itn=2), self.A, self.b, maxiter=2)
        self.assertFalse(verdict["valid"])
        self.assertIn("iteration limit", verdict["reason"])

    def test_rejects_excessive_residual(self):
        verdict = bench.validate_lsmr_result(
            self.result(x=[0.0, 0.0], normr=math.sqrt(5.0)),
            self.A, self.b, maxiter=2)
        self.assertFalse(verdict["valid"])
        self.assertIn("relative residual", verdict["reason"])

    def test_rejects_nonfinite_solution_or_diagnostic(self):
        for result in (
                self.result(x=[math.nan, 0.0]),
                self.result(normar=math.inf)):
            with self.subTest(result=result):
                verdict = bench.validate_lsmr_result(
                    result, self.A, self.b, maxiter=2)
                self.assertFalse(verdict["valid"])
                self.assertIn("non-finite", verdict["reason"])

    def test_accepts_finite_compatible_solution(self):
        for istop in (0, 1, 4):
            with self.subTest(istop=istop):
                verdict = bench.validate_lsmr_result(
                    self.result(istop=istop), self.A, self.b, maxiter=2)
                self.assertTrue(verdict["valid"], verdict["reason"])
                self.assertEqual(verdict["istop"], istop)
                self.assertEqual(verdict["iterations"], 1)
                self.assertEqual(verdict["relative_residual"], 0.0)


class OutputSchemaTests(unittest.TestCase):
    def row(self, **overrides):
        values = {
            "case_id": "grouped_vs_lsmr.8x2",
            "family": "grouped_vs_lsmr", "baseline_kind": "lsmr",
            "baseline_name": "LSMR",
            "numerical_contract": "router and baseline are valid",
            "historical_claim": "reference observation",
            "historical_claim_scope": {"driver": "gelsy"},
            "historical_claim_applicable": True,
            "m": 8, "n": 2, "note": "", "status": "UNIQUE",
            "rank": 2, "rank_lo": 2, "rank_hi": 2, "berr": 1e-16,
            "router_timings": [2.0, 4.0, 3.0],
            "baseline_timings": [1.0, 1.5, 2.0],
            "numerical_valid": True, "validation_reason": "ok",
            "historical_range": (0.2, 0.4),
        }
        values.update(overrides)
        return bench.make_result_row(**values)

    def test_lapack_names_follow_selected_driver(self):
        self.assertEqual(bench.baseline_name("lapack", "gelsy"), "DGELSY")
        self.assertEqual(bench.baseline_name("lapack", "gelsd"), "DGELSD")
        self.assertEqual(bench.baseline_name("lsmr", "gelsd"), "LSMR")

    def test_row_uses_neutral_baseline_fields_and_explicit_ratio_direction(self):
        row = self.row()

        self.assertNotIn("lapack_s", row)
        self.assertEqual(row["schema_version"], 2)
        self.assertEqual(row["baseline_name"], "LSMR")
        self.assertEqual(row["router_s"], 3.0)
        self.assertEqual(row["baseline_s"], 1.5)
        self.assertEqual(row["ratio_direction"], "baseline_over_router")
        self.assertEqual(row["baseline_over_router"], 0.5)
        self.assertEqual(row["router_timings_s"], [2.0, 4.0, 3.0])
        self.assertEqual(row["baseline_timings_s"], [1.0, 1.5, 2.0])
        self.assertEqual(row["router_mad_s"], 1.0)
        self.assertEqual(row["baseline_mad_s"], 0.5)

    def test_historical_timing_miss_does_not_fail_portable_validation(self):
        row = self.row(
            case_id="grouped_vs_lapack.8x2", family="grouped_vs_lapack",
            baseline_kind="lapack", baseline_name="DGELSY",
            router_timings=[1.0], baseline_timings=[100.0],
            historical_range=(12.0, 25.0))

        self.assertEqual(row["performance_observation"], "outside-reference-range")
        self.assertEqual(bench.portable_failures([row]), [])

    def test_grouped_reference_ranges_are_exact_and_observational(self):
        cases = bench.build_cases(np.random.default_rng(1), 1.0, False)
        lapack = next(c for c in cases if c["family"] == "grouped_vs_lapack")
        lsmr = next(c for c in cases if c["family"] == "grouped_vs_lsmr")

        self.assertEqual(lapack["historical_range"], (12.0, 25.0))
        self.assertEqual(lsmr["historical_range"], (1.0 / 5.9, 1.0 / 2.6))
        self.assertEqual(lapack["expected_status"], "UNIQUE")
        self.assertEqual(lsmr["expected_status"], "UNIQUE")

    def test_gelsd_grouped_lapack_row_is_driver_aware_everywhere(self):
        case = next(
            case for case in bench.build_cases(
                np.random.default_rng(1), 1.0, False)
            if case["family"] == "grouped_vs_lapack")
        comparison = bench.comparison_contract(case, "gelsd", 1.0)
        row = bench.make_result_row(
            case_id=case["case_id"], family=case["family"],
            baseline_kind="lapack", m=case["m"], n=case["n"], note="",
            status="UNIQUE", rank=case["n"], rank_lo=case["n"],
            rank_hi=case["n"], berr=1e-16, router_timings=[1.0],
            baseline_timings=[10.0], numerical_valid=True,
            validation_reason="ok", **comparison)

        self.assertEqual(row["baseline_name"], "DGELSD")
        self.assertNotIn("DGELSY", row["numerical_contract"])
        self.assertFalse(row["historical_claim_applicable"])

    def test_scaled_case_does_not_use_original_historical_range(self):
        case = next(
            case for case in bench.build_cases(
                np.random.default_rng(1), 0.5, False)
            if case["family"] == "grouped_vs_lapack")
        comparison = bench.comparison_contract(case, "gelsy", 0.5)
        row = bench.make_result_row(
            case_id=case["case_id"], family=case["family"],
            baseline_kind="lapack", m=case["m"], n=case["n"], note="",
            status="UNIQUE", rank=case["n"], rank_lo=case["n"],
            rank_hi=case["n"], berr=1e-16, router_timings=[1.0],
            baseline_timings=[100.0], numerical_valid=True,
            validation_reason="ok", **comparison)

        self.assertEqual(row["performance_observation"], "not-scoped")
        self.assertIsNone(row["historical_ratio_min"])
        self.assertIsNone(row["historical_ratio_max"])


class MetadataTests(unittest.TestCase):
    def test_metadata_is_machine_scoped_and_copies_verified_build_record(self):
        inputs = eligibility_inputs()
        inputs["threadpools"][0]["filepath"] = "/tmp/build/libblas.so"
        document = bench.build_metadata_document(
            timestamp_utc="2026-09-11T12:00:00Z",
            source_state=inputs["source_state"],
            argv=["experiments/synthetic_bench.py", "--driver", "gelsy"],
            args=inputs["args"], rows=inputs["rows"],
            machine=inputs["machine"], threadpools=inputs["threadpools"],
            software=inputs["software"],
            thread_control=inputs["thread_control"],
            build_verification=inputs["build_verification"])

        self.assertEqual(document["schema_version"], 2)
        self.assertEqual(document["scope"],
                         "reference-machine-performance-observation")
        self.assertEqual(document["source"]["git_sha"], "a" * 40)
        self.assertEqual(document["source"]["git_tree_sha"], "b" * 40)
        self.assertFalse(document["source"]["git_dirty"])
        self.assertEqual(document["benchmark"]["repeats"], 11)
        self.assertEqual(document["benchmark"]["case_warmups"], 1)
        self.assertEqual(document["benchmark"]["process_warmups"], 3)
        self.assertEqual(document["benchmark"]["summary_statistic"], "median")
        self.assertEqual(document["benchmark"]["dispersion_statistic"],
                         "median-absolute-deviation")
        self.assertEqual(document["machine"]["reference_name"],
                         "reference-host")
        self.assertNotIn("filepath", document["linear_algebra"]["threadpools"][0])
        self.assertEqual(document["build_provenance"],
                         inputs["build_verification"])
        self.assertEqual(document["command"],
                         "python3 experiments/synthetic_bench.py --driver gelsy")
        self.assertEqual(document["command_argv"],
                         ["experiments/synthetic_bench.py", "--driver",
                          "gelsy"])
        self.assertTrue(document["publication_eligibility"]["eligible"])

    def test_unknown_source_dirty_state_remains_unknown(self):
        args = SimpleNamespace(seed=17, repeats=5, driver="gelsy",
                               scale=1.0, no_large=True,
                               reference_machine=None)
        document = bench.build_metadata_document(
            timestamp_utc="2026-09-11T12:00:00Z",
            source_state={"git_sha": None, "git_tree_sha": None,
                          "git_dirty": None},
            argv=["experiments/synthetic_bench.py"], args=args, rows=[],
            machine={}, threadpools=[], software={}, thread_control={},
            build_verification={"verified": False,
                                "reasons": ["build_manifest_missing"],
                                "manifest": None})

        self.assertIsNone(document["source"]["git_dirty"])
        self.assertFalse(document["publication_eligibility"]["eligible"])
        for reason in ("reference_machine_missing", "source_git_sha_invalid",
                       "source_git_tree_invalid", "source_git_dirty_unknown",
                       "case_set_empty", "build_manifest_missing"):
            self.assertIn(reason,
                          document["publication_eligibility"]["reasons"])


class BuildManifestTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.router = self.root / "libaffine_bundle_solver.so"
        self.openblas = self.root / "libscipy_openblas.so"
        self.build_script = self.root / "build.sh"
        self.manifest_path = self.root / ".abs-build-manifest.json"
        self.router.write_bytes(b"router-binary")
        self.openblas.write_bytes(b"openblas-binary")
        self.build_script.write_bytes(b"#!/bin/sh\n")
        self.manifest = {
            "schema_version": 1,
            "built_at_utc": "2026-09-11T12:00:00Z",
            "source": {
                "git_sha": "a" * 40,
                "git_tree_sha": "b" * 40,
                "git_dirty": False,
            },
            "build_script": {
                "path": "build.sh", "sha256": digest(self.build_script),
            },
            "compiler": {
                "command_argv": ["ccache", "gcc"],
                "identity": "gcc test",
            },
            "router": {
                "compile_argv": ["ccache", "gcc", "-O3", "-c",
                                 "src/bsolver.c"],
                "link_argv": ["ccache", "gcc", "-shared",
                              str(self.openblas.resolve())],
                "arch_flags": "-march=native",
                "library": {
                    "basename": self.router.name,
                    "resolved_path": str(self.router.resolve()),
                    "sha256": digest(self.router),
                },
            },
            "openblas": {
                "basename": self.openblas.name,
                "resolved_path": str(self.openblas.resolve()),
                "sha256": digest(self.openblas),
            },
        }

    def tearDown(self):
        self.tempdir.cleanup()

    def write_manifest(self, manifest=None):
        self.manifest_path.write_text(json.dumps(
            self.manifest if manifest is None else manifest))

    def verify(self):
        return bench.verify_build_manifest(
            router_path=self.router, manifest_path=self.manifest_path,
            build_script_path=self.build_script,
            benchmark_git_sha="a" * 40,
            benchmark_git_tree_sha="b" * 40)

    def test_missing_or_invalid_manifest_is_rejected(self):
        missing = self.verify()
        self.assertFalse(missing["verified"])
        self.assertIn("build_manifest_missing", missing["reasons"])

        self.manifest_path.write_text("not JSON")
        invalid_json = self.verify()
        self.assertIn("build_manifest_invalid_json", invalid_json["reasons"])

        self.write_manifest({"schema_version": 999})
        invalid_schema = self.verify()
        self.assertIn("build_manifest_schema_invalid",
                      invalid_schema["reasons"])

    def test_manifest_identity_mismatches_are_all_reported(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["source"]["git_sha"] = "c" * 40
        manifest["source"]["git_tree_sha"] = "d" * 40
        manifest["source"]["git_dirty"] = True
        manifest["build_script"]["sha256"] = "0" * 64
        manifest["router"]["library"]["sha256"] = "1" * 64
        manifest["openblas"]["sha256"] = "2" * 64
        self.write_manifest(manifest)

        verification = self.verify()

        self.assertFalse(verification["verified"])
        self.assertEqual(
            verification["reasons"],
            ["router_library_hash_mismatch", "build_source_sha_mismatch",
             "build_source_tree_mismatch", "build_source_dirty",
             "build_script_hash_mismatch", "openblas_hash_mismatch"])

    def test_missing_compiler_commands_and_openblas_hash_are_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["compiler"] = {"command_argv": [], "identity": None}
        manifest["router"]["compile_argv"] = []
        manifest["router"]["link_argv"] = []
        manifest["openblas"]["sha256"] = None
        self.write_manifest(manifest)

        verification = self.verify()

        self.assertEqual(
            verification["reasons"],
            ["build_compiler_command_missing", "build_compiler_identity_missing",
             "router_compile_argv_missing", "router_link_argv_missing",
             "openblas_hash_missing"])

    def test_openblas_record_must_match_the_link_argv(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["router"]["link_argv"].remove(
            str(self.openblas.resolve()))
        self.write_manifest(manifest)

        verification = self.verify()

        self.assertIn("openblas_link_argv_mismatch",
                      verification["reasons"])

    def test_valid_manifest_matches_exact_router_and_dependencies(self):
        self.write_manifest()
        verification = self.verify()

        self.assertTrue(verification["verified"])
        self.assertEqual(verification["reasons"], [])
        self.assertEqual(verification["router_sha256"], digest(self.router))
        self.assertEqual(verification["manifest"], self.manifest)


class PublicationEligibilityTests(unittest.TestCase):
    def evaluate(self, **overrides):
        return bench.evaluate_publication_eligibility(
            **eligibility_inputs(**overrides))

    def test_complete_verified_reference_run_is_eligible(self):
        self.assertEqual(self.evaluate(), {"eligible": True, "reasons": []})

    def test_case_set_failures_are_distinguished(self):
        canonical = complete_rows()
        variants = {
            "empty": ([], "case_set_empty"),
            "incomplete": (canonical[:-1], "case_set_incomplete"),
            "duplicate": (canonical[:-1] + [canonical[0]],
                          "case_set_duplicate"),
            "reordered": ([canonical[1], canonical[0], *canonical[2:]],
                          "case_order_mismatch"),
            "unexpected": ([{**canonical[0], "case_id": "unexpected"},
                            *canonical[1:]], "case_set_unexpected"),
        }
        for name, (rows, reason) in variants.items():
            with self.subTest(name=name):
                verdict = self.evaluate(rows=rows)
                self.assertFalse(verdict["eligible"])
                self.assertIn(reason, verdict["reasons"])

    def test_numerical_and_timing_failures_are_all_reported(self):
        rows = complete_rows()
        rows[0]["numerical_valid"] = False
        rows[1].pop("router_timings_s")
        rows[2]["baseline_timings_s"] = rows[2]["baseline_timings_s"][:-1]
        rows[3]["router_timings_s"][0] = math.nan
        rows[4]["baseline_timings_s"][0] = 0.0
        rows[5]["router_s"] = math.inf
        rows[6]["baseline_s"] = -1.0
        rows[7]["baseline_over_router"] = math.nan
        rows[8]["ratio_direction"] = "router_over_baseline"

        verdict = self.evaluate(rows=rows)

        self.assertFalse(verdict["eligible"])
        self.assertEqual(
            verdict["reasons"],
            ["numerical_contract_failed", "timing_array_missing",
             "timing_repeat_count_mismatch", "timing_nonfinite",
             "timing_nonpositive", "timing_summary_nonfinite",
             "timing_summary_nonpositive", "timing_ratio_invalid"])

    def test_row_schema_must_be_current(self):
        rows = complete_rows()
        rows[0]["schema_version"] = 1
        self.assertIn("row_schema_invalid",
                      self.evaluate(rows=rows)["reasons"])

    def test_threading_machine_and_software_failures_are_all_reported(self):
        verdict = self.evaluate(
            thread_control={"OMP_NUM_THREADS": "2"},
            threadpools=[{"user_api": "blas", "internal_api": "openblas",
                          "num_threads": 2}],
            machine={}, software={})

        self.assertFalse(verdict["eligible"])
        for reason in (
                "thread_control_not_one:OMP_NUM_THREADS",
                "thread_control_missing:OPENBLAS_NUM_THREADS",
                "thread_control_missing:MKL_NUM_THREADS",
                "thread_control_missing:VECLIB_MAXIMUM_THREADS",
                "blas_threadpool_not_single_thread",
                "machine_identity_missing:cpu_model",
                "software_identity_missing:python",
                "software_identity_missing:numpy",
                "software_identity_missing:scipy"):
            self.assertIn(reason, verdict["reasons"])

    def test_missing_blas_provider_and_build_manifest_are_rejected(self):
        verdict = self.evaluate(
            threadpools=[],
            build_verification={
                "verified": False,
                "reasons": ["build_manifest_missing"],
                "manifest": None,
            })

        self.assertFalse(verdict["eligible"])
        self.assertIn("blas_provider_missing", verdict["reasons"])
        self.assertIn("build_manifest_missing", verdict["reasons"])

    def test_existing_configuration_and_source_blockers_are_preserved(self):
        args = SimpleNamespace(
            seed=1, repeats=3, driver="gelsy", scale=0.5,
            no_large=True, reference_machine="")
        source_state = {
            "git_sha": None, "git_tree_sha": None, "git_dirty": None,
        }

        verdict = self.evaluate(args=args, source_state=source_state)

        for reason in (
                "reference_machine_missing", "source_git_sha_invalid",
                "source_git_tree_invalid", "source_git_dirty_unknown",
                "scale_not_one", "large_cases_disabled",
                "insufficient_repeats"):
            self.assertIn(reason, verdict["reasons"])


class ClaimSchemaV2Tests(unittest.TestCase):
    def test_full_case_builder_matches_the_ordered_reference_signature(self):
        cases = bench.build_cases(np.random.default_rng(1), 1.0, True)
        actual = tuple(
            (case["case_id"], case["m"], case["n"],
             case.get("baseline_kind",
                      "lu" if case["m"] == case["n"] else "lapack"))
            for case in cases)
        self.assertEqual(actual, bench.CANONICAL_REFERENCE_SIGNATURE)

    def test_historical_claims_are_separate_and_scoped_for_all_shapes(self):
        cases = bench.build_cases(np.random.default_rng(1), 1.0, False)
        families = ("tall", "grouped_vs_lapack", "square", "wide")
        for family in families:
            with self.subTest(family=family):
                case = next(item for item in cases if item["family"] == family)
                contract = bench.comparison_contract(case, "gelsy", 1.0)
                self.assertNotIn("20-80", contract["numerical_contract"])
                self.assertTrue(contract["historical_claim_applicable"])
                scope = contract["historical_claim_scope"]
                self.assertEqual(scope["scale"], 1.0)
                self.assertEqual(scope["driver"], "gelsy")
                self.assertEqual(scope["dimensions"],
                                 {"m": case["reference_m"],
                                  "n": case["reference_n"]})

    def test_gelsd_and_scaled_claims_are_not_applicable(self):
        cases = bench.build_cases(np.random.default_rng(1), 1.0, False)
        for family in ("tall", "grouped_vs_lapack", "square", "wide"):
            case = next(item for item in cases if item["family"] == family)
            with self.subTest(family=family, configuration="gelsd"):
                contract = bench.comparison_contract(case, "gelsd", 1.0)
                self.assertFalse(contract["historical_claim_applicable"])
            with self.subTest(family=family, configuration="scaled"):
                contract = bench.comparison_contract(case, "gelsy", 0.5)
                self.assertFalse(contract["historical_claim_applicable"])

    def test_case_ids_distinguish_both_near_transition_cases(self):
        cases = bench.build_cases(np.random.default_rng(1), 1.0, False)
        transitions = [case for case in cases
                       if case["family"] == "near_transition"]
        self.assertEqual(len(transitions), 2)
        self.assertEqual(len({case["case_id"] for case in transitions}), 2)
        self.assertTrue(any("1e-12" in case["case_id"] for case in transitions))
        self.assertTrue(any("1e-10" in case["case_id"] for case in transitions))


if __name__ == "__main__":
    unittest.main()
