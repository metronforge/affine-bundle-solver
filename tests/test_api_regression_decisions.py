from pathlib import Path
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api_regression_binding import default_policy, load_library
from api_regression_corpus import discover_cases, load_manifest
from api_regression_decisions import (
    derive_conditions,
    emit_reachability_cnf,
    find_mcdc_pairs,
    policy_variants,
)
from api_regression_runner import call_combined


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/api-regression"


class DecisionModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = load_library(ROOT)
        cls.cases = discover_cases(CORPUS, load_manifest(CORPUS))
        cls.by_id = {case.case_id: case for case in cls.cases}

    def observe(self, case_id, policy_name):
        policy = policy_variants(self.library)[policy_name]
        return call_combined(self.by_id[case_id], policy, library=self.library)

    def test_derives_required_atomic_conditions(self):
        vector = derive_conditions(self.observe("T8-036", "default"), "default")
        for name in (
            "valid_input", "backend_success", "rank_resolved",
            "operational_compatible", "full_column_rank", "unique_quality",
            "unique_generator_success", "unique_verifier_success", "unique_eta_finite",
            "infinite_generator_success", "infinite_verifier_success", "infinite_eta_finite",
            "inconsistent_generator_success", "inconsistent_verifier_success",
            "inconsistent_eta_finite",
        ):
            self.assertIn(name, vector.conditions)

    def test_cnf_rejects_impossible_status_and_profile_combinations(self):
        cnf = emit_reachability_cnf()
        valid = cnf.example_assignment()
        self.assertTrue(cnf.satisfies(valid))
        two_statuses = dict(valid, status_unique=True, status_infinite=True)
        self.assertFalse(cnf.satisfies(two_statuses))
        accepted_without_finite_eta = dict(
            valid,
            unique_profile_accepted=True,
            unique_generator_success=True,
            unique_verifier_success=True,
            unique_eta_finite=False,
        )
        self.assertFalse(cnf.satisfies(accepted_without_finite_eta))

    def test_real_mcdc_pairs_change_only_target_condition_and_decision(self):
        observations = []
        for case_id, policy_name in (
            ("T8-001", "default"), ("T8-001", "tight_compatibility"),
            ("T8-022", "default"), ("T8-022", "wide_rank_band"),
            ("T8-036", "default"), ("T8-036", "tight_quality"),
        ):
            observations.append(derive_conditions(self.observe(case_id, policy_name), policy_name))
        coverage = find_mcdc_pairs(observations)
        self.assertEqual(
            {"operational_compatible", "rank_resolved", "unique_quality"},
            set(coverage.pairs),
        )
        for target, pair in coverage.pairs.items():
            scoped = coverage.decision_conditions[pair.decision]
            changed = {
                name for name in scoped
                if pair.left.conditions[name] != pair.right.conditions[name]
            }
            self.assertEqual({target}, changed)
            self.assertNotEqual(pair.left.decisions[pair.decision], pair.right.decisions[pair.decision])

    def test_uncovered_conditions_are_explicit(self):
        coverage = find_mcdc_pairs([])
        self.assertIn("valid_input", coverage.uncovered)
        self.assertIn("backend_success", coverage.uncovered)
        self.assertIn("full_column_rank", coverage.uncovered)
        self.assertIn("unique_generator_success", coverage.uncovered)

    def test_generated_traceability_report_names_real_scope_and_required_columns(self):
        report = (ROOT / "reports/api-regression/baseline-report.md").read_text()
        for text in (
            "условие API | MC/DC-пара | abs-apps slot IDs | хеши входов | ожидаемые выходы/оракул | тест | CI job",
            "26 square, 8 tall, and 2 wide",
            "blockprefix_final_1000.json",
            "V31-001..027",
            "T8-012, T8-013, T8-016, and T8-017",
            "not_exposed_by_current_api",
        ):
            self.assertIn(text, report)
        payload = json.loads((ROOT / "reports/api-regression/mcdc.json").read_text())
        self.assertEqual("real abs-apps Task8 fixtures only", payload["source"])
        self.assertEqual(
            {"operational_compatible", "rank_resolved", "unique_quality"},
            set(payload["pairs"]),
        )


if __name__ == "__main__":
    unittest.main()
