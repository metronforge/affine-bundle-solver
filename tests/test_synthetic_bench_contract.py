#!/usr/bin/env python3
"""Focused contract tests for the portable synthetic benchmark harness."""

import json
import math
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments import synthetic_bench as bench


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
    def test_lapack_names_follow_selected_driver(self):
        self.assertEqual(bench.baseline_name("lapack", "gelsy"), "DGELSY")
        self.assertEqual(bench.baseline_name("lapack", "gelsd"), "DGELSD")
        self.assertEqual(bench.baseline_name("lsmr", "gelsd"), "LSMR")

    def test_row_uses_neutral_baseline_fields_and_explicit_ratio_direction(self):
        row = bench.make_result_row(
            family="grouped_vs_lsmr", claim="reference observation",
            baseline_name="LSMR", m=8, n=2, note="",
            status="UNIQUE", rank=2, rank_lo=2, rank_hi=2,
            berr=1e-16, router_timings=[2.0, 4.0, 3.0],
            baseline_timings=[1.0, 1.5, 2.0], numerical_valid=True,
            validation_reason="ok", historical_range=(0.2, 0.4))

        self.assertNotIn("lapack_s", row)
        self.assertEqual(row["schema_version"], 1)
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
        row = bench.make_result_row(
            family="grouped_vs_lapack", claim="reference observation",
            baseline_name="DGELSY", m=8, n=2, note="",
            status="UNIQUE", rank=2, rank_lo=2, rank_hi=2,
            berr=1e-16, router_timings=[1.0], baseline_timings=[100.0],
            numerical_valid=True, validation_reason="ok",
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
            family=case["family"], m=case["m"], n=case["n"], note="",
            status="UNIQUE", rank=case["n"], rank_lo=case["n"],
            rank_hi=case["n"], berr=1e-16, router_timings=[1.0],
            baseline_timings=[10.0], numerical_valid=True,
            validation_reason="ok", **comparison)

        self.assertIn("DGELSD", row["claim"])
        self.assertNotIn("DGELSY", json.dumps(row, sort_keys=True))

    def test_scaled_case_does_not_use_original_historical_range(self):
        case = next(
            case for case in bench.build_cases(
                np.random.default_rng(1), 0.5, False)
            if case["family"] == "grouped_vs_lapack")
        comparison = bench.comparison_contract(case, "gelsy", 0.5)
        row = bench.make_result_row(
            family=case["family"], m=case["m"], n=case["n"], note="",
            status="UNIQUE", rank=case["n"], rank_lo=case["n"],
            rank_hi=case["n"], berr=1e-16, router_timings=[1.0],
            baseline_timings=[100.0], numerical_valid=True,
            validation_reason="ok", **comparison)

        self.assertEqual(row["performance_observation"], "not-scoped")
        self.assertIsNone(row["historical_ratio_min"])
        self.assertIsNone(row["historical_ratio_max"])


class MetadataTests(unittest.TestCase):
    def test_metadata_is_machine_scoped_and_omits_library_paths(self):
        args = SimpleNamespace(seed=17, repeats=5, driver="gelsy",
                               scale=1.0, no_large=True,
                               reference_machine="lab-host-01")
        document = bench.build_metadata_document(
            timestamp_utc="2026-09-11T12:00:00Z",
            source_git_sha="a" * 40, git_dirty=False,
            argv=["experiments/synthetic_bench.py", "--driver", "gelsy"],
            args=args, rows=[{"family": "wide", "m": 1, "n": 2,
                              "berr": math.nan}],
            machine={"cpu_model": "test cpu"},
            compiler={"identity": None, "flags": None},
            threadpools=[{"internal_api": "openblas", "num_threads": 1,
                          "filepath": "/tmp/build/libblas.so"}],
            software={"python": "3", "numpy": "2", "scipy": "1"},
            thread_control={"OMP_NUM_THREADS": "1"})

        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["scope"],
                         "reference-machine-performance-observation")
        self.assertEqual(document["source"]["git_sha"], "a" * 40)
        self.assertFalse(document["source"]["git_dirty"])
        self.assertEqual(document["benchmark"]["repeats"], 5)
        self.assertEqual(document["benchmark"]["case_warmups"], 1)
        self.assertEqual(document["benchmark"]["process_warmups"], 3)
        self.assertEqual(document["benchmark"]["summary_statistic"], "median")
        self.assertEqual(document["benchmark"]["dispersion_statistic"],
                         "median-absolute-deviation")
        self.assertEqual(document["machine"]["reference_name"], "lab-host-01")
        self.assertNotIn("filepath", document["linear_algebra"]["threadpools"][0])
        self.assertIsNone(document["results"][0]["berr"])
        self.assertEqual(document["command"],
                         "python3 experiments/synthetic_bench.py --driver gelsy")
        self.assertEqual(document["command_argv"],
                         ["experiments/synthetic_bench.py", "--driver",
                          "gelsy"])
        self.assertFalse(document["publication_eligibility"]["eligible"])
        self.assertEqual(
            document["publication_eligibility"]["reasons"],
            ["large_cases_disabled", "insufficient_repeats"])

    def test_unknown_source_dirty_state_remains_unknown(self):
        args = SimpleNamespace(seed=17, repeats=5, driver="gelsy",
                               scale=1.0, no_large=True,
                               reference_machine=None)
        document = bench.build_metadata_document(
            timestamp_utc="2026-09-11T12:00:00Z",
            source_git_sha=None, git_dirty=None,
            argv=["experiments/synthetic_bench.py"], args=args, rows=[],
            machine={}, compiler={}, threadpools=[], software={},
            thread_control={})

        self.assertIsNone(document["source"]["git_dirty"])
        self.assertFalse(document["publication_eligibility"]["eligible"])
        self.assertEqual(
            document["publication_eligibility"]["reasons"],
            ["reference_machine_missing", "source_git_sha_invalid",
             "source_git_dirty_unknown", "large_cases_disabled",
             "insufficient_repeats"])

    def test_clean_canonical_run_is_publication_eligible(self):
        args = SimpleNamespace(seed=17, repeats=11, driver="gelsy",
                               scale=1.0, no_large=False,
                               reference_machine="lab-host-01")
        document = bench.build_metadata_document(
            timestamp_utc="2026-09-11T12:00:00Z",
            source_git_sha="a" * 40, git_dirty=False,
            argv=["experiments/synthetic_bench.py"], args=args, rows=[],
            machine={}, compiler={}, threadpools=[], software={},
            thread_control={})

        self.assertTrue(document["publication_eligibility"]["eligible"])
        self.assertEqual(document["publication_eligibility"]["reasons"], [])

    def test_dirty_scaled_run_records_each_publication_blocker(self):
        args = SimpleNamespace(seed=17, repeats=11, driver="gelsy",
                               scale=0.5, no_large=False,
                               reference_machine=" ")
        document = bench.build_metadata_document(
            timestamp_utc="2026-09-11T12:00:00Z",
            source_git_sha="not-a-sha", git_dirty=True,
            argv=["experiments/synthetic_bench.py"], args=args, rows=[],
            machine={}, compiler={}, threadpools=[], software={},
            thread_control={})

        self.assertFalse(document["publication_eligibility"]["eligible"])
        self.assertEqual(
            document["publication_eligibility"]["reasons"],
            ["reference_machine_missing", "source_git_sha_invalid",
             "source_git_dirty", "scale_not_one"])

    def test_compiler_metadata_separates_effective_router_build_flags(self):
        with mock.patch.dict(
                os.environ,
                {"CC": "gcc", "ARCH_FLAGS": "-march=x86-64",
                 "CFLAGS": "-funroll-loops"}, clear=True):
            compiler = bench._compiler_info()

        self.assertEqual(
            compiler["router_build"]["effective_compile_flags"],
            ["-O3", "-march=x86-64", "-fopenmp", "-fPIC",
             "-ffast-math", "-Iinclude", "-Isrc", "-DABS_SCIPY_BLAS"])
        self.assertEqual(compiler["router_build"]["arch_flags"],
                         "-march=x86-64")
        self.assertEqual(compiler["environment_flags"]["CFLAGS"],
                         "-funroll-loops")
        self.assertNotIn(
            "-funroll-loops",
            compiler["router_build"]["effective_compile_flags"])

    def test_compiler_identity_is_unknown_when_cc_was_not_preserved(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            compiler = bench._compiler_info()

        self.assertIsNone(compiler["command"])
        self.assertIsNone(compiler["identity"])
        self.assertEqual(compiler["router_build"]["arch_flags"],
                         "-march=native")


if __name__ == "__main__":
    unittest.main()
