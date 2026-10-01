from __future__ import annotations

import ctypes
import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from api_regression_binding import (
    CandidateCheckResult, DP, default_policy, invoke_candidate_check, load_library
)


class SplitApiDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = load_library()

    def test_threshold_condition_independently_changes_verdict(self):
        policy = default_policy(self.library)
        A = np.eye(2)
        b = np.array([1.0, 2.0])
        ok_code, ok = invoke_candidate_check(self.library, A, b, b, policy)
        bad_code, bad = invoke_candidate_check(
            self.library, A, b, np.array([1.0, 2.001]), policy
        )
        self.assertEqual((0, 1), (ok_code, ok.verdict))
        self.assertEqual((0, 2), (bad_code, bad.verdict))
        self.assertTrue(math.isfinite(ok.max_abs_residual_up))
        self.assertTrue(math.isfinite(bad.max_abs_residual_up))
        self.assertLessEqual(ok.mixed_backward_error_up, policy.quality_threshold)
        self.assertGreater(bad.mixed_backward_error_up, policy.quality_threshold)

    def test_backward_bound_availability_changes_verdict(self):
        policy = default_policy(self.library)
        smallest = np.nextafter(0.0, 1.0)
        code, result = invoke_candidate_check(
            self.library,
            np.array([[smallest]]), np.array([0.0]), np.array([0.5]), policy,
        )
        self.assertEqual(0, code)
        self.assertEqual(0, result.verdict)
        self.assertTrue(math.isfinite(result.max_abs_residual_up))
        self.assertTrue(math.isinf(result.mixed_backward_error_up))

    def test_each_reachable_validation_condition_blocks_evaluation(self):
        policy = default_policy(self.library)
        A = np.eye(1, dtype=np.float64)
        b = np.ones(1, dtype=np.float64)
        x = np.ones(1, dtype=np.float64)
        cases = [
            (None, b.ctypes.data_as(DP), x.ctypes.data_as(DP), 1, 1, ctypes.byref(policy)),
            (A.ctypes.data_as(DP), None, x.ctypes.data_as(DP), 1, 1, ctypes.byref(policy)),
            (A.ctypes.data_as(DP), b.ctypes.data_as(DP), None, 1, 1, ctypes.byref(policy)),
            (A.ctypes.data_as(DP), b.ctypes.data_as(DP), x.ctypes.data_as(DP), 0, 1, ctypes.byref(policy)),
            (A.ctypes.data_as(DP), b.ctypes.data_as(DP), x.ctypes.data_as(DP), 1, 0, ctypes.byref(policy)),
            (A.ctypes.data_as(DP), b.ctypes.data_as(DP), x.ctypes.data_as(DP), 1, 1, None),
        ]
        for arguments in cases:
            result = CandidateCheckResult()
            self.library.bs_init_candidate_check_result(ctypes.byref(result))
            code = self.library.abs_check_candidate(
                *arguments, ctypes.byref(result)
            )
            self.assertEqual(1, code)
            self.assertEqual(0, result.verdict)
        bad_x = np.array([np.nan])
        code, result = invoke_candidate_check(self.library, A, b, bad_x, policy)
        self.assertEqual(1, code)
        self.assertEqual(0, result.verdict)


if __name__ == "__main__":
    unittest.main()
