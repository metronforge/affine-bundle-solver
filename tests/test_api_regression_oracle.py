import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api_regression_binding import default_policy, load_library
from api_regression_corpus import discover_cases, load_manifest
from api_regression_oracle import adjudicate, load_oracles, verify_semantic_layers
from api_regression_runner import call_combined


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/api-regression"


class ExactOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = discover_cases(CORPUS, load_manifest(CORPUS))
        cls.by_id = {case.case_id: case for case in cls.cases}

    def assert_oracle(self, case_id, rank_a, rank_augmented, status):
        result = adjudicate(self.by_id[case_id])
        self.assertEqual((rank_a, rank_augmented, status), (
            result.rank_a, result.rank_augmented, result.exact_status
        ))
        self.assertNotIn("numerical", result.method)

    def test_representative_shapes_and_transitions(self):
        for values in (
            ("T8-001", 14, 14, "INFINITE"),
            ("T8-008", 21, 21, "INFINITE"),
            ("T8-010", 35, 35, "INFINITE"),
            ("T8-019", 16, 16, "UNIQUE"),
            ("T8-023", 16, 16, "UNIQUE"),
            ("T8-026", 16, 16, "UNIQUE"),
            ("T8-029", 16, 16, "UNIQUE"),
        ):
            with self.subTest(case_id=values[0]):
                self.assert_oracle(*values)

    def test_semantic_disagreement_four_are_exactly_inconsistent(self):
        for case_id, rank in (("T8-012", 31), ("T8-013", 31), ("T8-016", 15), ("T8-017", 15)):
            with self.subTest(case_id=case_id):
                self.assert_oracle(case_id, rank, rank + 1, "INCONSISTENT")

    def test_external_inputs_have_exact_not_solver_derived_classes(self):
        expected = {
            "T8-030": (32, 33, "INCONSISTENT"),
            "T8-031": (32, 32, "UNIQUE"),
            "T8-032": (32, 32, "UNIQUE"),
            "T8-036": (48, 48, "UNIQUE"),
            "T8-037": (66, 66, "UNIQUE"),
            "T8-038": (132, 132, "UNIQUE"),
            "T8-039": (153, 153, "UNIQUE"),
        }
        for case_id, values in expected.items():
            with self.subTest(case_id=case_id):
                self.assert_oracle(case_id, *values)

    def test_persisted_oracles_cover_exact_hash_bound_corpus(self):
        records = load_oracles(CORPUS / "oracles.json")
        self.assertEqual(set(self.by_id), set(records))
        for case_id, case in self.by_id.items():
            record = records[case_id]
            self.assertEqual(case.metadata["A_bytes_sha256"], record.A_sha256)
            self.assertEqual(case.metadata["b_bytes_sha256"], record.b_sha256)
            self.assertEqual(adjudicate(case), record)

    def test_api_layers_do_not_replace_exact_oracle(self):
        library = load_library(ROOT)
        records = load_oracles(CORPUS / "oracles.json")
        for case_id in ("T8-012", "T8-013", "T8-016", "T8-017"):
            observation = call_combined(
                self.by_id[case_id], default_policy(library), library=library
            )
            checks = verify_semantic_layers(observation, records[case_id])
            self.assertTrue(all(check.passed for check in checks), checks)
            self.assertEqual("INCONSISTENT", records[case_id].exact_status)
            self.assertEqual("UNKNOWN", observation.exact_source.status)

    def test_all_api_semantic_layers_are_internally_consistent(self):
        library = load_library(ROOT)
        records = load_oracles(CORPUS / "oracles.json")
        for case in self.cases:
            with self.subTest(case_id=case.case_id):
                observation = call_combined(
                    case, default_policy(library), library=library
                )
                failed = [
                    check
                    for check in verify_semantic_layers(observation, records[case.case_id])
                    if not check.passed
                ]
                self.assertEqual([], failed)


if __name__ == "__main__":
    unittest.main()
