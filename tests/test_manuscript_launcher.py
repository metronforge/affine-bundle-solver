"""Fail closed on mutable or malformed toolchain references, before Docker."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ManuscriptLauncherTests(unittest.TestCase):
    def test_mutable_or_malformed_image_cannot_reach_docker(self):
        launcher = ROOT / "scripts/build_manuscript_container.sh"
        self.assertTrue(launcher.is_file(), "host manuscript launcher is missing")
        with tempfile.TemporaryDirectory(prefix="abs-launcher-") as temporary:
            root = Path(temporary)
            (root / "scripts").mkdir()
            (root / "ci/texlive").mkdir(parents=True)
            target = root / "scripts/build_manuscript_container.sh"
            shutil.copyfile(launcher, target)
            for image in (
                "ghcr.io/metronforge/affine-bundle-solver-texlive:latest",
                "ghcr.io/metronforge/affine-bundle-solver-texlive@sha256:bad",
                "",
            ):
                with self.subTest(image=image):
                    (root / "ci/texlive/image.txt").write_text(image + "\n")
                    result = subprocess.run(["bash", str(target)], text=True,
                                            capture_output=True, timeout=5)
                    self.assertEqual(2, result.returncode, result.stdout + result.stderr)
                    self.assertIn("invalid immutable TeX image reference", result.stderr)


if __name__ == "__main__":
    unittest.main()
