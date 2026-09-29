"""Snapshots must reject changed contracts and incomplete evidence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from compare_builds import (compare_snapshots, corpus_hash, semantic_key,
                            snapshot_cases, SNAPSHOT_SEEDS, validate_snapshot)


class SnapshotContract(unittest.TestCase):
    def fixture(self):
        return {"schema": 1, "corpus_sha256": corpus_hash(), "cases": [
            {"case": name, "seed": seed,
             "router": {"status": 1, "certainty": 1, "rank": 2,
                        "rank_lo": 2, "rank_hi": 2, "classification": 1},
             "certified_status": 1, "certified_rank": 2,
             "certified_rank_interval": [2, 2], "accepted_status_mask": 1,
             "verification": [0, 1, 1], "generation": [0, 1, 1]}
            for name, *_ in snapshot_cases() for seed in SNAPSHOT_SEEDS]}

    def test_local_key_excludes_numeric_diagnostics(self):
        a = [1, 1, 2, 2, 2, 1e-16, 2e-16, 1, 0, 1, 0]
        b = [1, 1, 2, 2, 2, 3e-16, 5e-16, 2, 1, 1, 1]
        self.assertEqual(semantic_key(a), semantic_key(b))
        b[2] = 3
        self.assertNotEqual(semantic_key(a), semantic_key(b))

    def test_missing_duplicate_and_invalid_evidence(self):
        good = self.fixture()
        bad_values = []
        v = copy.deepcopy(good); v["cases"].pop(); bad_values.append(v)
        v = copy.deepcopy(good); v["cases"][1] = v["cases"][0]; bad_values.append(v)
        v = copy.deepcopy(good); v["corpus_sha256"] = "wrong"; bad_values.append(v)
        v = copy.deepcopy(good); v["cases"][0]["router"].pop("rank"); bad_values.append(v)
        v = copy.deepcopy(good); v["cases"][0]["verification"] = []; bad_values.append(v)
        for v in bad_values:
            with self.assertRaises(ValueError):
                validate_snapshot(v)

    def test_comparator_rejects_semantic_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = [Path(directory) / name for name in ("a.json", "b.json")]
            good = self.fixture()
            a.write_text(json.dumps(good)); b.write_text(json.dumps(good))
            self.assertEqual(compare_snapshots([a, b]), 0)
            for field, changed in [("accepted_status_mask", 3),
                                   ("certified_rank_interval", [1, 2]),
                                   ("verification", [1, 1, 1]),
                                   ("certified_status", 5)]:
                v = copy.deepcopy(good); v["cases"][0][field] = changed
                b.write_text(json.dumps(v))
                self.assertEqual(compare_snapshots([a, b]), 1)


if __name__ == "__main__":
    unittest.main()
