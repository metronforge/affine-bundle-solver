from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api_regression_qualification import (
    MODES,
    QualificationSummary,
    expected_invocations,
    qualify,
)


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/api-regression"


class QualificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = qualify(CORPUS, ROOT)

    def test_matrix_derived_invocation_count_and_exact_ids(self):
        self.assertEqual(180, expected_invocations(36))
        self.assertEqual(36, self.summary.unique_case_count)
        self.assertEqual(180, self.summary.expected_invocations)
        self.assertEqual(180, self.summary.attempted_invocations)
        self.assertEqual(180, self.summary.completed_invocations)
        self.assertEqual(0, self.summary.skipped_invocations)
        self.assertEqual(set(MODES), set(self.summary.mode_counts))
        self.summary.validate()

    def test_resource_and_identity_fields_are_present(self):
        self.assertGreater(self.summary.wall_seconds, 0.0)
        self.assertGreater(self.summary.peak_rss_kib, 0)
        self.assertTrue(self.summary.solver_commit)
        self.assertTrue(self.summary.solver_source_commit)
        self.assertEqual(
            {"libaffine_bundle_solver.so", "libcertified_solver.so", "libstatus_verifier.so"},
            set(self.summary.binary_sha256),
        )
        self.assertIn("OPENBLAS_NUM_THREADS", self.summary.thread_configuration)

    def test_zero_or_missing_mode_summary_is_rejected(self):
        payload = self.summary.to_dict()
        payload["completed_invocations"] = 0
        payload["mode_counts"] = {"combined_default": 0}
        broken = QualificationSummary.from_dict(payload)
        with self.assertRaisesRegex(ValueError, "completed|mode"):
            broken.validate()

    def test_separate_workflow_declares_schedule_main_manual_and_exact_counts(self):
        workflow = (ROOT / ".github/workflows/api-regression-qualification.yml").read_text()
        for required in (
            "branches: [main]",
            "schedule:",
            "workflow_dispatch:",
            "36 cases / 180 invocations / portable GCC",
            "--expect-unique-cases 36",
            "payload['completed_invocations'] == 180",
            "if-no-files-found: error",
        ):
            self.assertIn(required, workflow)


if __name__ == "__main__":
    unittest.main()
