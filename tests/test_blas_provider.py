"""Wrong or mixed providers must not earn independent-BLAS coverage."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from check_blas_provider import validate_provider


class ProviderContract(unittest.TestCase):
    def test_distinct_resolved_providers(self):
        reference = ["/usr/lib/x86_64-linux-gnu/blas/libblas.so.3.10.0",
                     "/usr/lib/x86_64-linux-gnu/lapack/liblapack.so.3.10.0"]
        openblas = ["/usr/lib/x86_64-linux-gnu/openblas-pthread/libopenblasp-r0.3.20.so"]
        validate_provider(reference, "reference")
        validate_provider(openblas, "openblas")
        for paths, expected in [(reference, "openblas"), (openblas, "reference"),
                                (reference + openblas, "reference"),
                                (reference + openblas, "openblas"),
                                (reference[:1], "reference"), ([], "openblas")]:
            with self.subTest(paths=paths, expected=expected):
                with self.assertRaises(ValueError):
                    validate_provider(paths, expected)


if __name__ == "__main__":
    unittest.main()
