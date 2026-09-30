"""Check generator accuracy against an independent high-precision method."""
import ctypes as ct
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from api_regression_binding import load_library, default_policy
from api_regression_corpus import discover_cases, load_manifest
from api_regression_runner import call_combined
from api_regression_svd_reference import reference

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'tests/fixtures/api-regression'


class Witness(ct.Structure):
    _fields_ = [('n', ct.c_int), ('x', ct.POINTER(ct.c_double)),
                ('z', ct.POINTER(ct.c_double))]


class SvdReferenceTests(unittest.TestCase):
    def test_realified_cases_against_high_precision_projector(self):
        library = load_library(ROOT)
        dp = ct.POINTER(ct.c_double)
        library.bs_generate_infinite_witness.argtypes = [dp, dp, ct.c_int, ct.c_int, ct.POINTER(Witness)]
        library.bs_infinite_witness_free.argtypes = [ct.POINTER(Witness)]
        library.bs_verify_infinite.argtypes = [dp, dp, ct.c_int, ct.c_int, ct.POINTER(Witness), dp]
        processed = []
        for case in discover_cases(CORPUS, load_manifest(CORPUS)):
            if case.case_id not in ('T8-030', 'T8-031', 'T8-032'):
                continue
            with self.subTest(case=case.case_id):
                ref = reference(case.A, case.b)
                refined = reference(case.A, case.b, digits=120)
                self.assertEqual(ref['pivot'], refined['pivot'])
                self.assertEqual(ref['sigma_min'], refined['sigma_min'])
                self.assertEqual(ref['canonical_radius'], refined['canonical_radius'])
                witness = Witness()
                rc = library.bs_generate_infinite_witness(
                    case.A.ctypes.data_as(dp), case.b.ctypes.data_as(dp),
                    *case.A.shape, ct.byref(witness))
                self.assertEqual(0, rc)
                try:
                    z = np.ctypeslib.as_array(witness.z, shape=(case.A.shape[1],)).copy()
                    # Well separated cluster, even though its internal gap is zero.
                    np.testing.assert_allclose(z, ref['z'], rtol=0, atol=2e-10)
                    eta = ct.c_double()
                    self.assertEqual(0, library.bs_verify_infinite(
                        case.A.ctypes.data_as(dp), case.b.ctypes.data_as(dp),
                        *case.A.shape, ct.byref(witness), ct.byref(eta)))
                    self.assertAlmostEqual(float(ref['canonical_radius']), eta.value, delta=1e-12)
                finally:
                    library.bs_infinite_witness_free(ct.byref(witness))
                result = call_combined(case, default_policy(library), library=library)
                self.assertEqual(0, result.certificate.infinite_generator_code)
                self.assertEqual(0, result.certificate.infinite_verifier_code)
                self.assertTrue(result.certificate.nearby_status_mask & 2)
                self.assertAlmostEqual(float(ref['canonical_radius']),
                                       result.certificate.eta_infinite, delta=1e-12)
                processed.append(case.case_id)
        self.assertEqual(['T8-030', 'T8-031', 'T8-032'], processed)


if __name__ == '__main__':
    unittest.main()
