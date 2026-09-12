#!/usr/bin/env python3
"""Focused contract tests for the portable synthetic benchmark harness."""

import copy
import csv
import hashlib
import json
import math
import os
import subprocess
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
from tests import check_paper_claims as paper_claims


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


HISTORICAL_CASE_IDS = {
    "tall.8000x32", "tall.7680x64", "tall.7680x128",
    "grouped_vs_lapack.16384x64", "grouped_vs_lsmr.16384x64",
    "grouped_vs_lapack.131072x64", "grouped_vs_lsmr.131072x64",
    "grouped_vs_lapack.16384x256", "grouped_vs_lsmr.16384x256",
    "square.256x256", "square.512x512", "wide.128x512",
    "wide.256x2048", "tall_large.8000x2000",
    "tall_large.20000x2000", "square_large.2000x2000",
    "wide_large.2000x8000",
}


def complete_rows(repeats=11):
    rows = []
    for case_id, m, n, baseline_kind in bench.CANONICAL_REFERENCE_SIGNATURE:
        historical = case_id in HISTORICAL_CASE_IDS
        baseline = {"lapack": "DGELSY", "lu": "DGESV",
                    "lsmr": "LSMR"}[baseline_kind]
        diagnostics = None
        if baseline_kind == "lsmr":
            diagnostics = {
                "valid": True, "reason": "ok", "istop": 1,
                "iterations": 1, "relative_residual": 0.0,
                "reported_normr": 0.0, "reported_normar": 0.0,
                "reported_norma": 1.0, "reported_conda": 1.0,
                "reported_normx": 1.0,
            }
        status = "UNIQUE"
        rank = min(m, n)
        rank_lo = rank
        rank_hi = rank
        berr = 1e-16
        if case_id.startswith(("wide.", "wide_extreme.", "wide_large.")):
            status = "INFINITE"
            rank = rank_lo = rank_hi = m
            berr = math.nan
        elif case_id == "rank_deficient.4000x64":
            status, rank, rank_lo, rank_hi, berr = \
                "INFINITE", 40, 40, 64, math.nan
        elif case_id == "rank_deficient_large.6000x2000":
            status, rank, rank_lo, rank_hi, berr = \
                "INFINITE", 1500, 1500, 2000, math.nan
        elif case_id == "inconsistent.4000x64":
            status, rank, rank_lo, rank_hi, berr = \
                "INCONSISTENT", 64, 64, 64, math.nan
        elif case_id == "cond_1e+14.4000x64":
            status, rank, rank_lo, rank_hi, berr = \
                "UNDECIDABLE", 47, 47, 64, math.nan
        elif case_id == "cond_large_1e+14.6000x2000":
            status, rank, rank_lo, rank_hi, berr = \
                "UNDECIDABLE", 1416, 1416, 1982, math.nan
        elif case_id == "near_transition_large.eps_1e-11":
            status, rank, rank_lo, rank_hi, berr = \
                "UNDECIDABLE", 1999, 1999, 2000, math.nan
        elif case_id.startswith("near_transition."):
            status, rank, rank_lo, rank_hi, berr = \
                "UNDECIDABLE", 11, 11, 12, math.nan
        rows.append({
            "schema_version": 2,
            "case_id": case_id,
            "family": case_id.split(".", 1)[0],
            "m": m,
            "n": n,
            "baseline_kind": baseline_kind,
            "baseline_name": baseline,
            "numerical_contract": "portable numerical contract",
            "historical_claim": ("reference observation"
                                 if historical else None),
            "historical_claim_scope": ({
                "dimensions": {"m": m, "n": n}, "scale": 1.0,
                "driver": "gelsy", "reference_baseline": baseline,
                "machine_scope": "named-reference-machine",
                "threading": "single-thread",
            } if historical else None),
            "historical_claim_applicable": historical,
            "note": "", "status": status, "rank": rank,
            "rank_lo": rank_lo, "rank_hi": rank_hi,
            "berr": berr,
            "numerical_valid": True,
            "validation_reason": "ok",
            "router_timings_s": [1.0] * repeats,
            "baseline_timings_s": [2.0] * repeats,
            "router_s": 1.0,
            "baseline_s": 2.0,
            "router_mad_s": 0.0,
            "baseline_mad_s": 0.0,
            "ratio_direction": "baseline_over_router",
            "baseline_over_router": 2.0,
            "historical_ratio_min": (0.1 if historical else None),
            "historical_ratio_max": (100.0 if historical else None),
            "performance_observation": ("inside-reference-range"
                                        if historical else "not-scoped"),
            "baseline_diagnostics": diagnostics,
        })
    return rows


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
             "num_threads": 1, "version": "1",
             "basename": "libscipy_openblas.so", "sha256": "c" * 64}
        ],
        "build_verification": {
            "verified": True, "reasons": [],
            "manifest": {"schema_version": 1,
                         "openblas": {"sha256": "c" * 64}},
        },
    }
    values.update(overrides)
    return values


def write_candidate_csv(path, rows):
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=bench.ROW_REQUIRED_FIELDS)
        writer.writeheader()
        for row in rows:
            encoded = {}
            for field in bench.ROW_REQUIRED_FIELDS:
                value = row.get(field)
                if isinstance(value, (dict, list)):
                    encoded[field] = json.dumps(value, sort_keys=True)
                elif value is None or (isinstance(value, float) and
                                       math.isnan(value)):
                    encoded[field] = ""
                else:
                    encoded[field] = value
            writer.writerow(encoded)


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
        with tempfile.TemporaryDirectory() as directory:
            library = Path(directory) / "libblas.so"
            library.write_bytes(b"runtime blas")
            inputs = eligibility_inputs()
            runtime_hash = digest(library)
            inputs["threadpools"][0].update(
                filepath=str(library), sha256=runtime_hash)
            inputs["build_verification"]["manifest"]["openblas"][
                "sha256"] = runtime_hash
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
                "compile_argv": ["ccache", "gcc", "-O3",
                                 "-march=native", "-c", "src/bsolver.c"],
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

    def test_arch_flags_must_match_compile_argv_at_the_build_position(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["router"]["arch_flags"] = "-march=haswell -mtune=generic"
        manifest["router"]["compile_argv"].extend(
            ["-march=haswell", "-mtune=generic"])
        self.write_manifest(manifest)

        verification = self.verify()

        self.assertIn("router_arch_flags_mismatch", verification["reasons"])

    def test_router_manifest_is_relocatable_by_hash_and_basename(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["router"]["library"]["resolved_path"] = \
            "/old/build/location/libaffine_bundle_solver.so"
        self.write_manifest(manifest)

        self.assertTrue(self.verify()["verified"])

    def test_recorded_openblas_path_is_only_an_observation(self):
        manifest = copy.deepcopy(self.manifest)
        old_path = "/old/build/location/libscipy_openblas.so"
        manifest["router"]["link_argv"][-1] = old_path
        manifest["openblas"]["resolved_path"] = old_path
        self.write_manifest(manifest)

        verification = self.verify()

        self.assertTrue(verification["verified"], verification["reasons"])

    def test_failed_build_invalidates_a_previous_manifest(self):
        source_script = ROOT / "build.sh"
        for failing_environment in ({"PYTHON": "false"}, {"CC": "false"}):
            with self.subTest(environment=failing_environment):
                root = self.root / ("case-" + next(iter(failing_environment)))
                root.mkdir()
                script = root / "build.sh"
                script.write_bytes(source_script.read_bytes())
                script.chmod(0o755)
                manifest = root / ".abs-build-manifest.json"
                manifest.write_text('{"stale": true}\n')
                environment = os.environ.copy()
                environment.update(failing_environment)

                completed = subprocess.run(
                    [str(script)], cwd=root, env=environment,
                    capture_output=True, text=True, timeout=30)

                self.assertNotEqual(completed.returncode, 0)
                self.assertFalse(manifest.exists())

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

    def test_seed_driver_and_required_historical_rows_are_canonical(self):
        seed_args = copy.copy(eligibility_inputs()["args"])
        seed_args.seed = 7
        driver_args = copy.copy(eligibility_inputs()["args"])
        driver_args.driver = "gelsd"
        rows = complete_rows()
        historical = next(row for row in rows
                          if row["historical_claim_applicable"])
        historical["historical_claim_applicable"] = False

        self.assertIn("benchmark_seed_noncanonical",
                      self.evaluate(args=seed_args)["reasons"])
        self.assertIn("benchmark_driver_noncanonical",
                      self.evaluate(args=driver_args)["reasons"])
        self.assertIn("row_historical_applicability_invalid",
                      self.evaluate(rows=rows)["reasons"])

    def test_every_row_schema_field_is_required(self):
        required = (
            "schema_version", "case_id", "family", "baseline_kind",
            "baseline_name", "numerical_contract", "historical_claim",
            "historical_claim_scope", "historical_claim_applicable", "m",
            "n", "note", "status", "rank", "rank_lo", "rank_hi", "berr",
            "numerical_valid", "validation_reason", "router_timings_s",
            "baseline_timings_s", "router_s", "baseline_s", "router_mad_s",
            "baseline_mad_s", "ratio_direction", "baseline_over_router",
            "historical_ratio_min", "historical_ratio_max",
            "performance_observation", "baseline_diagnostics")
        for field in required:
            with self.subTest(field=field):
                rows = complete_rows()
                rows[0].pop(field)
                self.assertIn(
                    f"row_required_field_missing:{field}",
                    self.evaluate(rows=rows)["reasons"])

    def test_row_types_and_canonical_cross_fields_are_validated(self):
        variants = {
            "family": ("wrong-family", "row_family_mismatch"),
            "baseline_kind": ("lsmr", "row_canonical_signature_mismatch"),
            "baseline_name": ("DGELSD", "row_baseline_name_mismatch"),
            "numerical_contract": ("", "row_field_invalid:numerical_contract"),
            "m": (0, "row_canonical_signature_mismatch"),
            "status": ("NOT_A_STATUS", "row_field_invalid:status"),
            "rank_hi": (-1, "row_rank_structure_invalid"),
            "berr": ("unknown", "row_field_invalid:berr"),
            "validation_reason": ("", "row_field_invalid:validation_reason"),
        }
        for field, (value, reason) in variants.items():
            with self.subTest(field=field):
                rows = complete_rows()
                rows[0][field] = value
                self.assertIn(reason, self.evaluate(rows=rows)["reasons"])

    def test_timing_medians_and_mads_are_recomputed(self):
        variants = {
            "router_s": (3.0, "row_timing_median_mismatch:router"),
            "baseline_s": (3.0, "row_timing_median_mismatch:baseline"),
            "router_mad_s": (1.0, "row_timing_mad_mismatch:router"),
            "baseline_mad_s": (1.0, "row_timing_mad_mismatch:baseline"),
        }
        for field, (value, reason) in variants.items():
            with self.subTest(field=field):
                rows = complete_rows()
                rows[0][field] = value
                self.assertIn(reason, self.evaluate(rows=rows)["reasons"])

    def test_historical_scope_and_lsmr_diagnostics_are_validated(self):
        rows = complete_rows()
        historical = next(row for row in rows
                          if row["historical_claim_applicable"])
        historical["historical_claim_scope"]["driver"] = "gelsd"
        lsmr = next(row for row in rows if row["baseline_kind"] == "lsmr")
        lsmr["baseline_diagnostics"]["istop"] = 7

        reasons = self.evaluate(rows=rows)["reasons"]

        self.assertIn("row_historical_scope_invalid", reasons)
        self.assertIn("row_lsmr_diagnostics_invalid", reasons)

    def test_runtime_blas_binary_must_match_build_manifest(self):
        mismatched = [{
            "user_api": "blas", "internal_api": "openblas", "version": "1",
            "num_threads": 1, "basename": "libopenblas.so",
            "sha256": "d" * 64,
        }]
        unavailable = [{
            "user_api": "blas", "internal_api": "openblas", "version": "1",
            "num_threads": 1, "basename": "libopenblas.so", "sha256": None,
        }]

        self.assertIn("runtime_blas_hash_mismatch",
                      self.evaluate(threadpools=mismatched)["reasons"])
        self.assertIn("runtime_blas_identity_unavailable",
                      self.evaluate(threadpools=unavailable)["reasons"])

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
        for reason in (
                "numerical_contract_failed", "timing_array_missing",
                "timing_repeat_count_mismatch", "timing_nonfinite",
                "timing_nonpositive", "timing_summary_nonfinite",
                "timing_summary_nonpositive", "timing_ratio_invalid"):
            self.assertIn(reason, verdict["reasons"])

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


class CanonicalNumericalSemanticsTests(unittest.TestCase):
    def test_numerical_valid_cannot_mask_wrong_status(self):
        rows = complete_rows()
        row = next(item for item in rows if item["case_id"] == "wide.128x512")
        row.update(status="UNIQUE", rank=128, rank_lo=128, rank_hi=128,
                   berr=1e-16, numerical_valid=True)

        self.assertIn("row_semantic_status_mismatch:wide.128x512",
                      bench.validate_schema_v2_row(row, 11))
        self.assertIn("row_semantic_status_mismatch:wide.128x512",
                      bench.portable_failures([row]))

    def test_rank_interval_cannot_contradict_case_contract(self):
        row = next(item for item in complete_rows()
                   if item["case_id"] == "rank_deficient.4000x64")
        row.update(rank=41, rank_lo=41, rank_hi=64, numerical_valid=True)

        self.assertIn("row_semantic_rank_mismatch:rank_deficient.4000x64",
                      bench.validate_schema_v2_row(row, 11))

    def test_nonunique_case_cannot_publish_solution_quality(self):
        row = next(item for item in complete_rows()
                   if item["case_id"] == "wide_extreme.32x12800")
        row.update(berr=1e-16, numerical_valid=True)

        self.assertIn("row_semantic_quality_mismatch:wide_extreme.32x12800",
                      bench.validate_schema_v2_row(row, 11))

    def test_well_conditioned_case_cannot_be_undecidable(self):
        row = next(item for item in complete_rows()
                   if item["case_id"] == "cond_1e+08.4000x64")
        row.update(status="UNDECIDABLE", rank=63, rank_lo=63, rank_hi=64,
                   berr=math.nan, numerical_valid=True)

        self.assertIn("row_semantic_status_mismatch:cond_1e+08.4000x64",
                      bench.validate_schema_v2_row(row, 11))

    def test_ill_conditioned_case_must_remain_undecidable(self):
        row = next(item for item in complete_rows()
                   if item["case_id"] == "cond_1e+14.4000x64")
        row.update(status="UNIQUE", rank=64, rank_lo=64, rank_hi=64,
                   berr=1e-16, numerical_valid=True)

        self.assertIn("row_semantic_status_mismatch:cond_1e+14.4000x64",
                      bench.validate_schema_v2_row(row, 11))

    def test_all_canonical_case_specific_semantics_are_accepted(self):
        for row in complete_rows():
            with self.subTest(case_id=row["case_id"]):
                semantic_reasons = [reason for reason in
                                    bench.validate_schema_v2_row(row, 11)
                                    if reason.startswith("row_semantic_")]
                self.assertEqual(semantic_reasons, [])

    def test_case_families_have_explicit_semantic_failures(self):
        representatives = (
            "tall.8000x32", "grouped_vs_lapack.16384x64",
            "square.256x256", "wide_extreme.32x12800",
            "cond_1e+08.4000x64", "rank_deficient.4000x64",
            "inconsistent.4000x64", "near_transition.eps_1e-12")
        for case_id in representatives:
            with self.subTest(case_id=case_id):
                row = next(item for item in complete_rows()
                           if item["case_id"] == case_id)
                row.update(status="FAIL", numerical_valid=True)
                self.assertTrue(any(reason.startswith(
                    "row_semantic_status_mismatch:") for reason in
                    bench.validate_schema_v2_row(row, 11)))

    def test_timing_range_miss_is_not_a_numerical_failure(self):
        row = complete_rows()[0]
        row["performance_observation"] = "outside-reference-range"
        row["baseline_over_router"] = 2.0

        self.assertFalse(any(reason.startswith("row_semantic_") for reason in
                             bench.validate_schema_v2_row(row, 11)))


class ManuscriptClaimCoverageTests(unittest.TestCase):
    def registry(self):
        self.assertTrue(hasattr(paper_claims,
                               "load_performance_claim_registry"))
        return paper_claims.load_performance_claim_registry()

    def synthetic_candidate_registry(self):
        registry = copy.deepcopy(self.registry())
        registry["candidate_artifact"]["source_sha"] = \
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT,
                text=True).strip()
        registry["candidate_artifact"]["source_tree"] = \
            subprocess.check_output(
                ["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT,
                text=True).strip()
        return registry

    def validate(self, registry):
        self.assertTrue(hasattr(paper_claims,
                               "validate_performance_claim_registry"))
        return paper_claims.validate_performance_claim_registry(
            registry, manuscript_text=(ROOT / "paper.tex").read_text())

    def fixture_rows(self):
        rows = complete_rows()
        candidate_ratios = {
            "wide_extreme.32x12800": 1.206144,
            "grouped_vs_lsmr.16384x64": 0.623705,
            "grouped_vs_lsmr.131072x64": 1.603333,
            "grouped_vs_lsmr.16384x256": 0.636454,
        }
        for row in rows:
            if isinstance(row["berr"], float) and math.isnan(row["berr"]):
                row["berr"] = None
            if row["case_id"] in candidate_ratios:
                ratio = candidate_ratios[row["case_id"]]
                row["baseline_timings_s"] = [ratio] * 11
                row["baseline_s"] = ratio
                row["baseline_mad_s"] = 0.0
                row["baseline_over_router"] = ratio
        return rows

    def write_candidate_package(self, root, registry, *, csv_rows=None,
                                metadata_rows=None):
        results = Path(root) / "results"
        results.mkdir()
        csv_path = results / "synthetic-reference.csv"
        metadata_path = results / "synthetic-reference.metadata.json"
        checksum_path = results / "synthetic-reference.sha256"
        metadata_rows = metadata_rows or self.fixture_rows()
        csv_rows = metadata_rows if csv_rows is None else csv_rows
        write_candidate_csv(csv_path, csv_rows)
        metadata = {
            "source": {
                "git_sha": registry["candidate_artifact"]["source_sha"],
                "git_tree_sha": registry["candidate_artifact"]["source_tree"],
                "git_dirty": False,
            },
            "benchmark": {
                "seed": bench.CANONICAL_SEED,
                "driver": bench.CANONICAL_DRIVER,
                "scale": 1.0,
                "repeats": 11,
                "large_cases": True,
            },
            "build_provenance": {
                "verified": True, "reasons": [],
                "router_sha256": "a" * 64,
                "manifest": {
                    "source": {
                        "git_sha":
                            registry["candidate_artifact"]["source_sha"],
                        "git_tree_sha":
                            registry["candidate_artifact"]["source_tree"],
                        "git_dirty": False,
                    },
                    "router": {"library": {"sha256": "a" * 64}},
                    "openblas": {"sha256": "b" * 64},
                },
            },
            "publication_eligibility": {"eligible": True, "reasons": []},
            "thread_control": {
                name: "1" for name in bench.REQUIRED_THREAD_CONTROLS},
            "linear_algebra": {"threadpools": [{
                "user_api": "blas", "num_threads": 1,
                "sha256": "b" * 64}]},
            "machine": {
                "cpu_model": "CPU", "physical_cores": 1,
                "logical_cores": 1, "ram_bytes": 1, "os": "Linux",
                "kernel": "test", "reference_name": "reference"},
            "software": {"python": "3", "numpy": "2", "scipy": "1"},
            "results": metadata_rows,
        }
        metadata_path.write_text(json.dumps(metadata, allow_nan=False))
        registry["candidate_artifact"]["csv"]["sha256"] = digest(csv_path)
        registry["candidate_artifact"]["metadata"]["sha256"] = \
            digest(metadata_path)
        checksum_path.write_text(
            f"{digest(csv_path)}  {csv_path.name}\n"
            f"{digest(metadata_path)}  {metadata_path.name}\n")
        registry["candidate_artifact"]["checksum"]["sha256"] = \
            digest(checksum_path)
        return metadata

    def rewrite_candidate_metadata(self, root, registry, metadata):
        results = Path(root) / "results"
        csv_path = results / "synthetic-reference.csv"
        metadata_path = results / "synthetic-reference.metadata.json"
        checksum_path = results / "synthetic-reference.sha256"
        metadata_path.write_text(json.dumps(metadata, allow_nan=False))
        registry["candidate_artifact"]["metadata"]["sha256"] = \
            digest(metadata_path)
        checksum_path.write_text(
            f"{digest(csv_path)}  {csv_path.name}\n"
            f"{digest(metadata_path)}  {metadata_path.name}\n")
        registry["candidate_artifact"]["checksum"]["sha256"] = \
            digest(checksum_path)

    def test_unmapped_manuscript_claim_is_fail_closed(self):
        registry = self.registry()
        registry["claims"] = registry["claims"][1:]

        self.assertTrue(any(reason.startswith("manuscript_claim_unmapped:")
                            for reason in self.validate(registry)))

    def test_extreme_wide_mapping_is_mandatory(self):
        registry = self.registry()
        registry["claims"] = [claim for claim in registry["claims"]
                              if claim["claim_id"] !=
                              "wide_extreme.32x12800"]

        self.assertIn("manuscript_claim_unmapped:wide_extreme.32x12800",
                      self.validate(registry))

    def test_ratio_direction_is_explicit_and_not_reversible(self):
        for value in (None, "router_over_dgelsy"):
            with self.subTest(value=value):
                registry = self.registry()
                claim = next(item for item in registry["claims"]
                             if item["claim_id"] ==
                             "wide_extreme.32x12800")
                claim["ratio_direction"] = value
                self.assertIn(
                    "claim_ratio_direction_invalid:wide_extreme.32x12800",
                    self.validate(registry))

    def test_unsupported_evidence_cannot_be_publication_ready(self):
        for evidence_class in ("historical-unconfirmed", "different-task",
                               "different-generator", "not-covered"):
            with self.subTest(evidence_class=evidence_class):
                registry = self.registry()
                claim = registry["claims"][0]
                claim["evidence_class"] = evidence_class
                claim["publication_status"] = "publication-ready"
                self.assertIn(
                    f"claim_unsupported_evidence_ready:{claim['claim_id']}",
                    self.validate(registry))

    def test_unknown_historical_machine_cannot_masquerade_as_current(self):
        registry = self.registry()
        claim = next(item for item in registry["claims"]
                     if item["claim_id"] == "wide_extreme.32x12800")
        claim["machine_protocol_scope"] = {
            "machine": "metronforge-laptop-ref-01",
            "protocol": "canonical-reference-v2"}

        self.assertIn(
            "claim_historical_scope_masquerades_as_current:"
            "wide_extreme.32x12800", self.validate(registry))

    def test_different_task_or_generator_is_not_direct_reproduction(self):
        for evidence_class in ("different-task", "different-generator"):
            with self.subTest(evidence_class=evidence_class):
                registry = self.registry()
                claim = registry["claims"][0]
                claim["evidence_class"] = evidence_class
                claim["task_relationship"] = "direct-reproduction"
                self.assertIn(
                    f"claim_evidence_not_direct:{claim['claim_id']}",
                    self.validate(registry))

    def test_three_verdicts_are_independent(self):
        self.assertTrue(hasattr(paper_claims, "evaluate_performance_claims"))
        verdicts = paper_claims.evaluate_performance_claims(
            self.registry(), benchmark_protocol={"eligible": True,
                                                 "reasons": []})

        self.assertEqual(verdicts["benchmark_protocol_eligibility"],
                         {"eligible": True, "reasons": []})
        self.assertTrue(verdicts["manuscript_claim_coverage"]["complete"])
        self.assertFalse(
            verdicts["manuscript_publication_readiness"]["ready"])
        self.assertIn("manuscript_blocker:wide_extreme.32x12800",
                      verdicts["manuscript_publication_readiness"]["reasons"])
        self.assertIn("manuscript_blocker:grouped.lsmr",
                      verdicts["manuscript_publication_readiness"]["reasons"])

    def test_known_manuscript_blockers_are_detected_exactly(self):
        verdicts = paper_claims.evaluate_performance_claims(
            self.registry(), benchmark_protocol={"eligible": True,
                                                 "reasons": []})
        expected = {
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
        self.assertEqual(set(verdicts[
            "manuscript_publication_readiness"]["reasons"]), expected)

    def test_artifact_case_mapping_is_structural_and_semantic(self):
        variants = (
            (None, "claim_artifact_mapping_invalid:grouped.dgelsy"),
            ([], "claim_artifact_mapping_invalid:grouped.dgelsy"),
            ("grouped_vs_lapack.16384x64",
             "claim_artifact_mapping_invalid:grouped.dgelsy"),
            ([123], "claim_artifact_mapping_invalid:grouped.dgelsy"),
            (["unknown.case"],
             "claim_artifact_mapping_unknown:grouped.dgelsy:unknown.case"),
            (["grouped_vs_lapack.16384x64"] * 2,
             "claim_artifact_mapping_duplicate:grouped.dgelsy"),
            (["grouped_vs_lapack.16384x256",
              "grouped_vs_lapack.131072x64",
              "grouped_vs_lapack.16384x64"],
             "claim_artifact_mapping_semantic_mismatch:grouped.dgelsy"),
        )
        for mapping, reason in variants:
            with self.subTest(mapping=mapping):
                registry = self.registry()
                claim = next(item for item in registry["claims"]
                             if item["claim_id"] == "grouped.dgelsy")
                claim["artifact_case_mapping"] = mapping
                self.assertIn(reason, self.validate(registry))

    def test_registry_entry_removal_never_crashes_artifact_audit(self):
        registry = self.registry()
        registry["claims"] = [claim for claim in registry["claims"]
                              if claim["claim_id"] !=
                              "wide_extreme.32x12800"]
        with tempfile.TemporaryDirectory() as directory:
            self.write_candidate_package(directory, registry)
            try:
                verdicts = paper_claims.audit_candidate_package(
                    directory, registry)
            except Exception as error:  # fail as an assertion, not a test error
                self.fail(f"audit raised instead of returning blockers: {error}")

        self.assertIn("manuscript_claim_unmapped:wide_extreme.32x12800",
                      verdicts["manuscript_claim_coverage"]["reasons"])

    def test_vague_historical_identity_is_not_publication_evidence(self):
        registry = self.registry()
        claim = registry["claims"][0]
        claim["evidence_class"] = "historical-confirmed"
        claim["historical_source_identity"] = "tracked result package"
        claim.pop("historical_provenance", None)
        claim["publication_status"] = "publication-ready"

        reasons = self.validate(registry)

        self.assertIn(
            f"claim_historical_confirmation_unsupported:{claim['claim_id']}",
            reasons)
        self.assertIn(
            f"claim_unsupported_evidence_ready:{claim['claim_id']}", reasons)

    def test_freshness_methodology_claim_is_mandatory(self):
        claim_id = "methodology.quantitative_results_freshness"
        self.assertIn(claim_id, paper_claims.REQUIRED_PERFORMANCE_CLAIM_IDS)
        registry = self.registry()
        registry["claims"] = [claim for claim in registry["claims"]
                              if claim["claim_id"] != claim_id]

        self.assertIn(f"manuscript_claim_unmapped:{claim_id}",
                      self.validate(registry))

    def test_tree_route_performance_claim_is_mandatory(self):
        claim_id = "parallel.bundle_tree_late_growth"

        self.assertIn(claim_id, paper_claims.REQUIRED_PERFORMANCE_CLAIM_IDS)

    def test_json_environment_and_raw_outputs_claim_is_mandatory(self):
        claim_id = "methodology.json_environment_raw_outputs"

        self.assertIn(claim_id, paper_claims.REQUIRED_PERFORMANCE_CLAIM_IDS)

    def test_malformed_candidate_rows_return_blockers(self):
        variants = (None, [], "not-a-row")
        for invalid_row in variants:
            with self.subTest(row=invalid_row), \
                    tempfile.TemporaryDirectory() as directory:
                registry = self.registry()
                metadata = self.write_candidate_package(directory, registry)
                metadata["results"][0] = invalid_row
                self.rewrite_candidate_metadata(directory, registry, metadata)

                try:
                    verdicts = paper_claims.audit_candidate_package(
                        directory, registry)
                except Exception as error:
                    self.fail(f"malformed row raised: {error}")
                self.assertIn("candidate_metadata_row_invalid:0",
                              verdicts["artifact_integrity"]["reasons"])

    def test_unhashable_case_id_returns_a_blocker(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = self.registry()
            metadata = self.write_candidate_package(directory, registry)
            metadata["results"][0]["case_id"] = ["unhashable"]
            self.rewrite_candidate_metadata(directory, registry, metadata)

            try:
                verdicts = paper_claims.audit_candidate_package(
                    directory, registry)
            except Exception as error:
                self.fail(f"unhashable case_id raised: {error}")
            self.assertIn("candidate_metadata_case_id_invalid:0",
                          verdicts["artifact_integrity"]["reasons"])

    def test_malformed_blas_pool_returns_a_blocker(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = self.registry()
            metadata = self.write_candidate_package(directory, registry)
            metadata["linear_algebra"]["threadpools"] = [None, [], "pool"]
            metadata["build_provenance"]["manifest"]["openblas"][
                "sha256"] = ["unhashable"]
            self.rewrite_candidate_metadata(directory, registry, metadata)

            try:
                verdicts = paper_claims.audit_candidate_package(
                    directory, registry)
            except Exception as error:
                self.fail(f"malformed BLAS pool raised: {error}")
            for index in range(3):
                self.assertIn(f"candidate_blas_pool_invalid:{index}",
                              verdicts[
                                  "benchmark_protocol_eligibility"]["reasons"])

    def test_malformed_artifact_registry_record_returns_blockers(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = self.registry()
            self.write_candidate_package(directory, registry)
            registry["candidate_artifact"]["checksum"] = ["invalid"]

            try:
                verdicts = paper_claims.audit_candidate_package(
                    directory, registry)
            except Exception as error:
                self.fail(f"malformed artifact record raised: {error}")
            self.assertIn("artifact_registry_record_invalid:checksum",
                          verdicts["artifact_integrity"]["reasons"])

    def test_malformed_candidate_faults_are_aggregated(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = self.registry()
            metadata = self.write_candidate_package(directory, registry)
            metadata["results"][0] = None
            metadata["results"][1]["case_id"] = ["unhashable"]
            metadata["linear_algebra"]["threadpools"] = [None]
            self.rewrite_candidate_metadata(directory, registry, metadata)
            registry["candidate_artifact"]["checksum"] = "invalid"
            confirmed = next(item for item in registry["claims"]
                             if item["claim_id"] == "grouped.dgelsy")
            confirmed.update(evidence_class="historical-confirmed",
                             publication_status="publication-ready")

            try:
                verdicts = paper_claims.audit_candidate_package(
                    directory, registry)
            except Exception as error:
                self.fail(f"fault aggregation raised: {error}")

            self.assertIn("artifact_registry_record_invalid:checksum",
                          verdicts["artifact_integrity"]["reasons"])
            self.assertIn("candidate_metadata_row_invalid:0",
                          verdicts["artifact_integrity"]["reasons"])
            self.assertIn("candidate_metadata_case_id_invalid:1",
                          verdicts["artifact_integrity"]["reasons"])
            self.assertIn("candidate_blas_pool_invalid:0",
                          verdicts[
                              "benchmark_protocol_eligibility"]["reasons"])
            self.assertIn(
                "claim_historical_confirmation_unsupported:grouped.dgelsy",
                verdicts["manuscript_claim_coverage"]["reasons"])

    def test_extreme_wide_contradiction_cannot_be_reclassified_ready(self):
        registry = self.registry()
        claim = next(item for item in registry["claims"]
                     if item["claim_id"] == "wide_extreme.32x12800")
        claim["evidence_class"] = "current-artifact"
        claim["publication_status"] = "publication-ready"

        self.assertIn(
            "claim_extreme_wide_contradiction_unresolved:"
            "wide_extreme.32x12800", self.validate(registry))

    def test_registry_validation_aggregates_independent_blockers(self):
        registry = self.registry()
        grouped = next(item for item in registry["claims"]
                       if item["claim_id"] == "grouped.dgelsy")
        grouped["artifact_case_mapping"] = ["unknown.case", "unknown.case"]
        extreme = next(item for item in registry["claims"]
                       if item["claim_id"] == "wide_extreme.32x12800")
        extreme["ratio_direction"] = "router_over_dgelsy"
        confirmed = registry["claims"][0]
        confirmed["evidence_class"] = "historical-confirmed"

        reasons = self.validate(registry)

        for reason in (
                "claim_artifact_mapping_unknown:grouped.dgelsy:unknown.case",
                "claim_artifact_mapping_duplicate:grouped.dgelsy",
                "claim_ratio_direction_invalid:wide_extreme.32x12800",
                "claim_historical_confirmation_unsupported:"
                f"{confirmed['claim_id']}"):
            self.assertIn(reason, reasons)

    def test_csv_and_metadata_rows_must_match_semantically(self):
        variants = {}
        rows = self.fixture_rows()
        variants["missing"] = (rows[:-1], "candidate_csv_row_missing")
        extra = copy.deepcopy(rows)
        extra.append({**copy.deepcopy(rows[-1]), "case_id": "unexpected.case"})
        variants["extra"] = (extra, "candidate_csv_row_extra")
        reordered = copy.deepcopy(rows)
        reordered[0], reordered[1] = reordered[1], reordered[0]
        variants["reordered"] = (reordered, "candidate_csv_order_mismatch")
        duplicated = copy.deepcopy(rows[:-1]) + [copy.deepcopy(rows[0])]
        variants["duplicated"] = (duplicated,
                                  "candidate_csv_case_duplicate")
        divergent = copy.deepcopy(rows)
        divergent[0]["note"] = "CSV differs from metadata"
        variants["divergent"] = (
            divergent, "candidate_csv_metadata_divergence:tall.8000x32")

        for name, (csv_rows, reason) in variants.items():
            with self.subTest(name=name), \
                    tempfile.TemporaryDirectory() as directory:
                registry = self.registry()
                self.write_candidate_package(
                    directory, registry, csv_rows=csv_rows,
                    metadata_rows=copy.deepcopy(rows))
                verdicts = paper_claims.audit_candidate_package(
                    directory, registry)
                self.assertFalse(verdicts["artifact_integrity"]["valid"])
                self.assertIn(reason,
                              verdicts["artifact_integrity"]["reasons"])

    def test_ci_runs_inventory_exact_candidate_and_strict_readiness(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()

        for required in (
                "--check-performance-inventory",
                "ed240df3cc0bd644996f475a6d0e77d95eb6c568",
                "67eef1fbda6f7486357cba200f01c9f355ac854a",
                'git fetch --no-tags --depth=1 origin "$PR34_HEAD"',
                'git fetch --no-tags --depth=1 origin "$PR34_SOURCE"',
                'git diff --exit-code "$PR34_HEAD"',
                "--audit-performance-artifacts .",
                "--require-publication-ready",
                "manuscript_blocker:parallel.bundle_tree_late_growth",
                "manuscript_blocker:methodology.json_environment_raw_outputs"):
            self.assertIn(required, workflow)
        self.assertNotIn("pull/34/head", workflow)
        self.assertNotIn("/tmp/pr34-candidate", workflow)

    def test_inventory_cli_runs_without_pythonpath(self):
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)

        completed = subprocess.run(
            [sys.executable, "tests/check_paper_claims.py",
             "--check-performance-inventory"],
            cwd=ROOT, env=environment, capture_output=True, text=True,
            check=False)

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_synthetic_candidate_fixture_integrity_and_readiness_are_separate(
            self):
        registry = self.synthetic_candidate_registry()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_candidate_package(root, registry)

            verdicts = paper_claims.audit_candidate_package(root, registry)

        self.assertEqual(verdicts["artifact_integrity"],
                         {"valid": True, "reasons": []})
        self.assertEqual(verdicts["benchmark_protocol_eligibility"],
                         {"eligible": True, "reasons": []})
        self.assertFalse(
            verdicts["manuscript_publication_readiness"]["ready"])
        self.assertIn("manuscript_blocker:wide_extreme.32x12800",
                      verdicts["manuscript_publication_readiness"]["reasons"])
        self.assertIn("manuscript_blocker:grouped.lsmr",
                      verdicts["manuscript_publication_readiness"]["reasons"])

    def test_malformed_nested_claim_values_return_stable_blockers(self):
        variants = (
            ("claims-null", lambda r: r.update(claims=None),
             "claim_registry_claims_invalid"),
            ("claims-scalar", lambda r: r.update(claims=7),
             "claim_registry_claims_invalid"),
            ("claims-dict", lambda r: r.update(claims={}),
             "claim_registry_claims_invalid"),
            ("unhashable-id", lambda r: r["claims"][0].update(claim_id=[]),
             "claim_id_invalid"),
            ("historical-observation",
             lambda r: next(c for c in r["claims"] if c["claim_id"] ==
                            "wide_extreme.32x12800").update(
                                historical_observation=[]),
             "claim_observation_invalid:wide_extreme.32x12800:"
             "historical_observation"),
            ("candidate-observation",
             lambda r: next(c for c in r["claims"] if c["claim_id"] ==
                            "wide_extreme.32x12800").update(
                                candidate_observation="invalid"),
             "claim_observation_invalid:wide_extreme.32x12800:"
             "candidate_observation"),
            ("grouped-observation",
             lambda r: next(c for c in r["claims"] if c["claim_id"] ==
                            "grouped.lsmr")["candidate_observation"].update(
                                lsmr_over_router=[0.6, "invalid", 0.7]),
             "claim_grouped_observation_invalid:grouped.lsmr"),
            ("manuscript-metadata", lambda r: r.update(manuscript=[]),
             "claim_registry_manuscript_invalid"),
        )
        for label, mutate, expected in variants:
            with self.subTest(label=label), \
                    tempfile.TemporaryDirectory() as directory:
                registry = self.registry()
                self.write_candidate_package(directory, registry)
                mutate(registry)
                try:
                    verdicts = paper_claims.audit_candidate_package(
                        directory, registry)
                except Exception as error:
                    self.fail(f"malformed claim data raised: {error}")
                all_reasons = (
                    verdicts["artifact_integrity"]["reasons"] +
                    verdicts["benchmark_protocol_eligibility"]["reasons"] +
                    verdicts["manuscript_claim_coverage"]["reasons"])
                self.assertIn(expected, all_reasons)

    def test_missing_or_nonnumeric_grouped_ratio_returns_stable_blocker(self):
        case_id = "grouped_vs_lsmr.16384x64"
        for value in (None, "not-a-number"):
            with self.subTest(value=value), \
                    tempfile.TemporaryDirectory() as directory:
                registry = self.registry()
                metadata = self.write_candidate_package(directory, registry)
                row = next(item for item in metadata["results"]
                           if item["case_id"] == case_id)
                if value is None:
                    row.pop("baseline_over_router")
                else:
                    row["baseline_over_router"] = value
                self.rewrite_candidate_metadata(directory, registry, metadata)
                try:
                    verdicts = paper_claims.audit_candidate_package(
                        directory, registry)
                except Exception as error:
                    self.fail(f"malformed grouped ratio raised: {error}")
                self.assertIn(
                    f"candidate_grouped_lsmr_ratio_invalid:{case_id}",
                    verdicts["benchmark_protocol_eligibility"]["reasons"])

    def test_historical_confirmation_is_explicitly_unsupported(self):
        registry = self.registry()
        claim = next(item for item in registry["claims"]
                     if item["claim_id"] == "grouped.dgelsy")
        claim.update(evidence_class="historical-confirmed",
                     publication_status="publication-ready")

        reasons = self.validate(registry)
        verdicts = paper_claims.evaluate_performance_claims(
            registry, benchmark_protocol={"eligible": True, "reasons": []})

        self.assertIn(
            "claim_historical_confirmation_unsupported:grouped.dgelsy",
            reasons)
        self.assertIn("manuscript_blocker:grouped.dgelsy",
                      verdicts["manuscript_publication_readiness"]["reasons"])

    def test_candidate_source_identity_is_git_verified(self):
        source_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        wrong_tree = subprocess.check_output(
            ["git", "rev-parse", "HEAD:tests"], cwd=ROOT,
            text=True).strip()
        variants = (
            (None, None, "candidate_source_identity_invalid"),
            ("not-a-sha", "also-not-a-tree",
             "candidate_source_identity_invalid"),
            ("0" * 40, "1" * 40, "candidate_source_commit_missing"),
            (source_sha, wrong_tree,
             "candidate_source_commit_tree_mismatch"),
        )
        for source, tree, expected in variants:
            with self.subTest(source=source, tree=tree), \
                    tempfile.TemporaryDirectory() as directory:
                registry = self.registry()
                registry["candidate_artifact"]["source_sha"] = source
                registry["candidate_artifact"]["source_tree"] = tree
                self.write_candidate_package(directory, registry)

                verdicts = paper_claims.audit_candidate_package(
                    directory, registry)

                self.assertIn(
                    expected,
                    verdicts["benchmark_protocol_eligibility"]["reasons"])

    def test_malformed_evidence_classes_return_blockers_not_exceptions(self):
        for value in (None, [], {}, True, 7):
            with self.subTest(value=value):
                registry = self.registry()
                claim = registry["claims"][0]
                claim["evidence_class"] = value
                try:
                    reasons = self.validate(registry)
                    verdicts = paper_claims.evaluate_performance_claims(
                        registry, benchmark_protocol={"eligible": True,
                                                      "reasons": []})
                except Exception as error:
                    self.fail(f"malformed evidence raised: {error}")
                self.assertIn(
                    f"claim_evidence_class_invalid:{claim['claim_id']}",
                    reasons)
                self.assertIn(
                    f"manuscript_blocker:{claim['claim_id']}",
                    verdicts["manuscript_publication_readiness"]["reasons"])

    def test_control_characters_in_git_paths_are_rejected_without_crash(self):
        for value in ("results/bad\x00.csv", "results/bad\x01.csv",
                      "results/bad\x7f.csv"):
            with self.subTest(path=repr(value)), \
                    tempfile.TemporaryDirectory() as directory:
                registry = self.registry()
                self.write_candidate_package(directory, registry)
                registry["candidate_artifact"]["csv"]["path"] = value
                try:
                    verdicts = paper_claims.audit_candidate_package(
                        directory, registry)
                except Exception as error:
                    self.fail(f"control-character path raised: {error}")
                self.assertIn(
                    "artifact_registry_path_invalid:csv",
                    verdicts["artifact_integrity"]["reasons"])

    def test_blas_hashes_and_thread_counts_are_strictly_typed(self):
        invalid_hashes = ("", "a" * 63, "g" * 64, ["a" * 64])
        for value in invalid_hashes:
            with self.subTest(hash=value), \
                    tempfile.TemporaryDirectory() as directory:
                registry = self.registry()
                metadata = self.write_candidate_package(directory, registry)
                pool = metadata["linear_algebra"]["threadpools"][0]
                pool["sha256"] = value
                metadata["build_provenance"]["manifest"]["openblas"][
                    "sha256"] = value
                self.rewrite_candidate_metadata(directory, registry, metadata)

                verdicts = paper_claims.audit_candidate_package(
                    directory, registry)

                self.assertIn(
                    "candidate_blas_pool_invalid:0",
                    verdicts["benchmark_protocol_eligibility"]["reasons"])

        for value in (True, False, 0, -1, "1", 1.0):
            with self.subTest(num_threads=value), \
                    tempfile.TemporaryDirectory() as directory:
                registry = self.registry()
                metadata = self.write_candidate_package(directory, registry)
                metadata["linear_algebra"]["threadpools"][0][
                    "num_threads"] = value
                self.rewrite_candidate_metadata(directory, registry, metadata)

                verdicts = paper_claims.audit_candidate_package(
                    directory, registry)

                self.assertIn(
                    "candidate_blas_pool_invalid:0",
                    verdicts["benchmark_protocol_eligibility"]["reasons"])

    def test_independent_malformed_faults_are_aggregated(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = self.registry()
            registry["candidate_artifact"]["source_sha"] = None
            registry["candidate_artifact"]["source_tree"] = None
            claim = registry["claims"][0]
            claim["evidence_class"] = []
            metadata = self.write_candidate_package(directory, registry)
            metadata["linear_algebra"]["threadpools"][0].update(
                sha256="bad", num_threads=True)
            self.rewrite_candidate_metadata(directory, registry, metadata)
            registry["candidate_artifact"]["csv"]["path"] = "bad\x00.csv"

            try:
                verdicts = paper_claims.audit_candidate_package(
                    directory, registry)
            except Exception as error:
                self.fail(f"independent malformed faults raised: {error}")

            combined = (
                verdicts["artifact_integrity"]["reasons"] +
                verdicts["benchmark_protocol_eligibility"]["reasons"] +
                verdicts["manuscript_claim_coverage"]["reasons"])
            for expected in (
                    "artifact_registry_path_invalid:csv",
                    "candidate_source_identity_invalid",
                    "candidate_blas_pool_invalid:0",
                    f"claim_evidence_class_invalid:{claim['claim_id']}"):
                self.assertIn(expected, combined)


if __name__ == "__main__":
    unittest.main()
