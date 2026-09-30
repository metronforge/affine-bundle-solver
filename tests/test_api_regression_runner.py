import math
import os
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api_regression_corpus import discover_cases, load_manifest, sha256_file
from api_regression_binding import default_policy, load_library
from api_regression_runner import (
    DEFAULT_FLOAT_ABS_TOL,
    DEFAULT_FLOAT_REL_TOL,
    ETA_INFINITE_REL_TOL,
    _assert_snapshot,
    call_combined,
    compare_value,
    run_corpus,
)


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "api-regression"


def _assert_child_success(testcase, result):
    testcase.assertEqual(
        0,
        result.returncode,
        "child exit code "
        f"{result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}",
    )


class ApiRegressionRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = load_library(ROOT)
        cls.cases = discover_cases(CORPUS, load_manifest(CORPUS))

    def case(self, case_id):
        return next(case for case in self.cases if case.case_id == case_id)

    def test_default_combined_call_matches_public_layout(self):
        policy = default_policy(self.library)
        self.assertEqual((1e-13, 1e-9, 2e-10, 1e-14), policy.values())
        observation = call_combined(self.case("T8-001"), policy, library=self.library)
        self.assertEqual(0, observation.return_code)
        self.assertEqual(observation.operational.status, observation.operational.raw_class)
        self.assertEqual("UNKNOWN", observation.exact_source.status)
        self.assertEqual("NOT_VERIFIED", observation.exact_source.verification)

    def test_tall_and_wide_dimensions_are_not_transposed(self):
        policy = default_policy(self.library)
        wide = call_combined(self.case("T8-008"), policy, library=self.library)
        tall = call_combined(self.case("T8-010"), policy, library=self.library)
        self.assertEqual((21, 24), wide.input_shape)
        self.assertEqual((75, 40), tall.input_shape)
        self.assertEqual(0, wide.return_code)
        self.assertEqual(0, tall.return_code)

    def test_run_summary_executes_all_discovered_ids(self):
        summary = run_corpus(CORPUS, library=self.library)
        self.assertEqual(36, summary.discovered_count)
        self.assertEqual(36, summary.attempted_count)
        self.assertEqual(36, summary.completed_count)
        self.assertEqual(summary.discovered_ids, summary.completed_ids)

    def test_no_solution_vector_is_reported_as_exposed(self):
        observation = call_combined(
            self.case("T8-001"), default_policy(self.library), library=self.library
        )
        self.assertEqual("not_exposed_by_current_api", observation.solution_vector)

    def test_partial_execution_fails(self):
        with self.assertRaisesRegex(ValueError, "missing.*T8-002"):
            run_corpus(CORPUS, library=self.library, include_ids={"T8-001"})

    def test_semantically_absent_fields_are_not_compared_as_numbers(self):
        self.assertTrue(compare_value(math.nan, math.nan))
        self.assertFalse(compare_value(math.nan, 0.0))
        self.assertFalse(compare_value(0.0, math.nan))

    def test_nearby_infinite_radius_uses_its_measured_cross_runner_tolerance(self):
        contract = load_manifest(CORPUS)["behavior_contract"]
        self.assertEqual(DEFAULT_FLOAT_REL_TOL, contract["float_tolerance"]["relative"])
        self.assertEqual(DEFAULT_FLOAT_ABS_TOL, contract["float_tolerance"]["absolute"])
        field_tolerance = contract["field_float_tolerance"]["certificate.eta_infinite"]
        self.assertEqual(ETA_INFINITE_REL_TOL, field_tolerance["relative"])
        self.assertEqual(DEFAULT_FLOAT_ABS_TOL, field_tolerance["absolute"])
        expected = {"certificate": {"eta_infinite": 0.0023273682262441543}}
        portable = {"certificate": {"eta_infinite": 0.0023350514905808558}}
        _assert_snapshot(portable, expected, "T8-030")
        outside_bound = {
            "certificate": {
                "eta_infinite": expected["certificate"]["eta_infinite"] * 1.006
            }
        }
        with self.assertRaisesRegex(AssertionError, "T8-030.certificate.eta_infinite"):
            _assert_snapshot(outside_bound, expected, "T8-030")

    def test_controlled_wrong_status_fails_and_names_case_and_field(self):
        manifest_path = CORPUS / "manifest.json"
        fixture_path = CORPUS / "inputs/T8-001.npz"
        before = (sha256_file(manifest_path), sha256_file(fixture_path))
        env = dict(os.environ)
        env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", ABS_CERT_UNIQUE_THREADS="1")
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tests/api_regression_runner.py"),
                "--expect-count", "36",
                "--expect-ids-from", "manifest",
                "--inject-wrong-expected", "T8-001:operational_status",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("T8-001", result.stderr)
        self.assertIn("operational_status", result.stderr)
        self.assertIn("controlled expectation mismatch", result.stderr)
        self.assertEqual(before, (sha256_file(manifest_path), sha256_file(fixture_path)))

    def test_child_failure_diagnostic_includes_exit_stdout_and_stderr(self):
        result = subprocess.CompletedProcess(
            args=["child"], returncode=7, stdout="captured-out", stderr="captured-err"
        )
        with self.assertRaisesRegex(
            AssertionError,
            "exit code 7.*captured-out.*captured-err",
        ):
            _assert_child_success(self, result)

    def test_cli_positive_run_reports_exact_complete_set(self):
        env = dict(os.environ)
        env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", ABS_CERT_UNIQUE_THREADS="1")
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tests/api_regression_runner.py"),
                "--expect-count", "36",
                "--expect-ids-from", "manifest",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        _assert_child_success(self, result)
        payload = __import__("json").loads(result.stdout)
        self.assertEqual(36, len(payload["discovered_ids"]))
        self.assertEqual(payload["discovered_ids"], payload["completed_ids"])

    def test_required_ci_contains_positive_and_controlled_negative_steps(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        for required in (
            "API regression baseline (36 cases)",
            "API regression controlled negative",
            "--expect-count 36 --expect-ids-from manifest",
            "--inject-wrong-expected T8-001:operational_status",
            "test_certificate_thread_determinism.py",
        ):
            self.assertIn(required, workflow)
        self.assertIn("pull_request:", workflow)
        self.assertIn("branches: [main]", workflow)


if __name__ == "__main__":
    unittest.main()
