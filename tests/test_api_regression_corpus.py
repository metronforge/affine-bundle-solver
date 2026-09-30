import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api_regression_corpus import CorpusError, discover_cases, load_manifest


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "api-regression"
EXPECTED_IDS = {
    *(f"T8-{i:03d}" for i in range(1, 33)),
    *(f"T8-{i:03d}" for i in range(36, 40)),
}


class CorpusIdentityTests(unittest.TestCase):
    def discover(self, root: Path = CORPUS):
        return discover_cases(root, load_manifest(root))

    def copied_corpus(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name) / "corpus"
        shutil.copytree(CORPUS, root)
        return temporary, root

    def test_discovers_exact_expected_ids(self):
        cases = self.discover()
        self.assertEqual(36, len(cases))
        self.assertEqual(EXPECTED_IDS, {case.case_id for case in cases})

    def test_shape_partition(self):
        cases = self.discover()
        counts = {"square": 0, "tall": 0, "wide": 0}
        for case in cases:
            m, n = case.A.shape
            counts["square" if m == n else "tall" if m > n else "wide"] += 1
        self.assertEqual({"square": 26, "tall": 8, "wide": 2}, counts)

    def test_missing_fixture_fails_with_id(self):
        temporary, root = self.copied_corpus()
        self.addCleanup(temporary.cleanup)
        (root / "inputs" / "T8-008.npz").unlink()
        with self.assertRaisesRegex(CorpusError, "T8-008"):
            self.discover(root)

    def test_same_shape_replacement_fails_hash(self):
        temporary, root = self.copied_corpus()
        self.addCleanup(temporary.cleanup)
        path = root / "inputs" / "T8-001.npz"
        with np.load(path, allow_pickle=False) as data:
            A, b = data["A"].copy(), data["b"].copy()
        A[0, 0] += 1.0
        np.savez(path, A=A, b=b)
        with self.assertRaisesRegex(CorpusError, "T8-001.*hash"):
            self.discover(root)

    def test_duplicate_manifest_id_fails(self):
        manifest = load_manifest(CORPUS)
        manifest["cases"].append(dict(manifest["cases"][0]))
        with self.assertRaisesRegex(CorpusError, "duplicate.*T8-001"):
            discover_cases(CORPUS, manifest)

    def test_nonfinite_or_wrong_dtype_fails(self):
        for replacement, message in (("float32", "binary64"), ("nan", "finite")):
            with self.subTest(replacement=replacement):
                temporary, root = self.copied_corpus()
                try:
                    path = root / "inputs" / "T8-001.npz"
                    with np.load(path, allow_pickle=False) as data:
                        A, b = data["A"].copy(), data["b"].copy()
                    if replacement == "float32":
                        A = A.astype(np.float32)
                    else:
                        A[0, 0] = np.nan
                    np.savez(path, A=A, b=b)
                    with self.assertRaisesRegex(CorpusError, message):
                        self.discover(root)
                finally:
                    temporary.cleanup()

    def test_manifest_declares_frozen_source_and_attribution(self):
        manifest = load_manifest(CORPUS)
        self.assertEqual(
            "ae9b662d7f5755418aa80f31ade1fffcbefebafd",
            manifest["source"]["commit"],
        )
        attribution_keys = {case["attribution"] for case in manifest["cases"]}
        self.assertEqual({"abs_apps", "rasg_bsd_2", "suitesparse_cc_by_4"}, attribution_keys)
        notices = (CORPUS / "THIRD_PARTY_NOTICES.md").read_text()
        for required in (
            "Radio Astronomy Software Group",
            "BSD 2-Clause",
            "SuiteSparse Matrix Collection",
            "CC BY 4.0",
            "10.1145/2049662.2049663",
            "10.21105/joss.01244",
            "J. Lewis",
        ):
            self.assertIn(required, notices)


if __name__ == "__main__":
    unittest.main()
