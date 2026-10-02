"""Verify offline TikZ, PGF, and PGFPlots support in the actual image."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TexLiveGraphicsContract(unittest.TestCase):
    def setUp(self):
        self.image = os.environ["MANUSCRIPT_IMAGE"]
        self.container_options = [
            "--rm", "--network=none", "--read-only", "--tmpfs",
            "/tmp:rw,nosuid,size=128m", "--cap-drop=ALL",
            "--security-opt=no-new-privileges", "--user",
            f"{os.getuid()}:{os.getgid()}", "--env", "HOME=/tmp",
        ]

    def run_container(self, *args, **kwargs):
        return subprocess.run(
            ["docker", "run", *self.container_options, *args],
            capture_output=True, text=True, timeout=120, **kwargs,
        )

    def test_tikz_pgf_and_pgfplots_files_are_installed(self):
        for filename in ("tikz.sty", "pgf.sty", "pgfplots.sty"):
            with self.subTest(filename=filename):
                result = self.run_container(self.image, "kpsewhich", filename)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertTrue(result.stdout.strip().endswith(filename), result.stdout)

    def test_graphics_fixture_compiles_offline_as_invoking_user(self):
        with tempfile.TemporaryDirectory(prefix="abs-texlive-graphics-") as temporary:
            workspace = Path(temporary)
            shutil.copyfile(
                ROOT / "tests/fixtures/texlive-graphics/qualification.tex",
                workspace / "qualification.tex",
            )
            result = self.run_container(
                "--mount", f"type=bind,source={workspace},target=/work",
                "--workdir", "/work", self.image, "pdflatex",
                "-interaction=nonstopmode", "-halt-on-error", "-file-line-error",
                "qualification.tex",
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            pdf = workspace / "qualification.pdf"
            self.assertTrue(pdf.read_bytes().startswith(b"%PDF-"))
            self.assertEqual(os.getuid(), pdf.stat().st_uid)


if __name__ == "__main__":
    unittest.main(verbosity=2)
