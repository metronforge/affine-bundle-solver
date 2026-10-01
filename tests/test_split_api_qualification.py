from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from split_api_qualification import qualify


class SplitApiQualificationTests(unittest.TestCase):
    def test_frozen_corpus_matrix(self):
        counts = qualify(Path(__file__).parent / "fixtures/api-regression")
        self.assertEqual(36, counts["solve"])
        self.assertEqual(36, counts["solve_candidate_check"])
        self.assertEqual(36, counts["certification"])
        self.assertEqual(36, counts["combined_vs_composed"])
        self.assertEqual(144, counts["caller_supplied_candidates"])
        self.assertEqual(180, counts["independent_quality_oracles"])
        self.assertEqual(36, counts["independent_solution_oracles"])


if __name__ == "__main__":
    unittest.main()
