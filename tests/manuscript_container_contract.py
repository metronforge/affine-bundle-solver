"""Opt-in integration checks against a real, offline manuscript container.

Run with MANUSCRIPT_IMAGE=<image> python tests/manuscript_container_contract.py.
No Docker mocks: missing TeX packages, lost exit codes and unresolved references
must fail the image qualification before it can be published.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ManuscriptContainerContract(unittest.TestCase):
    def setUp(self):
        self.image = os.environ["MANUSCRIPT_IMAGE"]
        self.temporary = tempfile.TemporaryDirectory(prefix="abs-manuscript-")
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        for name in ("paper.tex", "references.bib", "build_paper.sh"):
            shutil.copyfile(ROOT / name, self.workspace / name)

    def build(self):
        return subprocess.run(
            ["docker", "run", "--rm", "--network=none", "--read-only",
             "--tmpfs", "/tmp:rw,nosuid,size=128m", "--cap-drop=ALL",
             "--security-opt=no-new-privileges",
             "--user", f"{os.getuid()}:{os.getgid()}", "--env", "HOME=/tmp",
             "--mount", f"type=bind,source={self.workspace},target=/work",
             "--workdir", "/work", self.image, "abs-build-manuscript"],
            capture_output=True, text=True, timeout=120,
        )

    def test_real_manuscript_builds_offline_as_workspace_owner(self):
        result = self.build()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        pdf = self.workspace / "paper.pdf"
        self.assertTrue(pdf.read_bytes().startswith(b"%PDF-"))
        self.assertEqual(os.getuid(), pdf.stat().st_uid)
        self.assertIn("no unresolved references", result.stdout)

    def test_unresolved_reference_fails_even_when_latex_produces_pdf(self):
        manuscript = self.workspace / "paper.tex"
        manuscript.write_text(manuscript.read_text().replace(
            r"\end{document}",
            r"Unresolved probe: \ref{absMissingContainerProbe}." + "\n" + r"\end{document}"))
        result = self.build()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("manuscript has unresolved references or citations", result.stdout + result.stderr)
        self.assertTrue((self.workspace / "paper.pdf").exists())

    def test_latex_error_cannot_pass_with_stale_pdf(self):
        manuscript = self.workspace / "paper.tex"
        manuscript.write_text(r"\absUndefinedContainerProbe" + "\n" + manuscript.read_text())
        (self.workspace / "paper.pdf").write_bytes(b"%PDF-stale probe\n")
        result = self.build()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("manuscript compilation failed", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
