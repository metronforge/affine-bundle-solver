"""Regression: certificate radii must not depend materially on BLAS threads."""

import json
import math
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


def probe(corpus_mode=False):
    sys.path.insert(0, str(ROOT / "tests"))
    from api_regression_binding import default_policy, load_library
    from api_regression_corpus import discover_cases, load_manifest
    from api_regression_runner import call_combined, run_corpus, snapshot_observation

    corpus = ROOT / "tests/fixtures/api-regression"
    if corpus_mode:
        summary = run_corpus(corpus, library=load_library(ROOT))
        print(
            json.dumps(
                {item.case_id: snapshot_observation(item) for item in summary.observations},
                sort_keys=True,
            )
        )
        return
    case = next(
        case
        for case in discover_cases(corpus, load_manifest(corpus))
        if case.case_id == "T8-038"
    )
    library = load_library(ROOT)
    observation = call_combined(case, default_policy(library), library=library)
    print(
        json.dumps(
            {
                "status": observation.operational.status,
                "rank": observation.operational.rank,
                "mask": observation.certificate.nearby_status_mask,
                "eta_inconsistent": observation.certificate.eta_inconsistent,
                "generator_code": observation.certificate.inconsistent_generator_code,
                "verifier_code": observation.certificate.inconsistent_verifier_code,
            },
            sort_keys=True,
        )
    )


class CertificateThreadDeterminismTests(unittest.TestCase):
    def run_probe(self, threads, corpus_mode=False):
        env = dict(os.environ)
        env.update(
            OPENBLAS_NUM_THREADS=str(threads),
            OMP_NUM_THREADS=str(threads),
            ABS_CERT_UNIQUE_THREADS=str(threads),
        )
        output = subprocess.check_output(
            [sys.executable, __file__, "--probe-corpus" if corpus_mode else "--probe"],
            cwd=ROOT,
            env=env,
            text=True,
        )
        return json.loads(output)

    def test_t8_038_inconsistent_radius_is_thread_invariant(self):
        single = self.run_probe(1)
        self.assertEqual("UNIQUE", single["status"])
        self.assertEqual(132, single["rank"])
        self.assertEqual(7, single["mask"])
        self.assertEqual(0, single["generator_code"])
        self.assertEqual(0, single["verifier_code"])
        self.assertEqual(0.9999999890199766, single["eta_inconsistent"])
        for threads in (2, 4):
            with self.subTest(threads=threads):
                self.assertEqual(single, self.run_probe(threads))

    def assert_contract_equal(self, single, threaded, path="corpus"):
        if isinstance(single, dict):
            self.assertEqual(set(single), set(threaded), path)
            for key in single:
                self.assert_contract_equal(single[key], threaded[key], f"{path}.{key}")
        elif isinstance(single, list):
            self.assertEqual(len(single), len(threaded), path)
            for index, (left, right) in enumerate(zip(single, threaded)):
                self.assert_contract_equal(left, right, f"{path}[{index}]")
        elif isinstance(single, float):
            self.assertTrue(
                math.isclose(single, threaded, rel_tol=1e-10, abs_tol=1e-12),
                f"{path}: {single!r} != {threaded!r}",
            )
        else:
            self.assertEqual(single, threaded, path)

    def test_full_corpus_contract_is_thread_stable(self):
        self.assert_contract_equal(
            self.run_probe(1, corpus_mode=True), self.run_probe(2, corpus_mode=True)
        )


if __name__ == "__main__":
    if "--probe-corpus" in sys.argv:
        probe(corpus_mode=True)
    elif "--probe" in sys.argv:
        probe()
    else:
        unittest.main()
