import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api_regression_corpus import discover_cases, load_manifest
from api_regression_binding import default_policy, load_library
from api_regression_runner import compare_value, call_combined, run_corpus


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "api-regression"


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


if __name__ == "__main__":
    unittest.main()
