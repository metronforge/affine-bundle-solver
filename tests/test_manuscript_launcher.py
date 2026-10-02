"""Fail closed on mutable or malformed toolchain references, before Docker."""
from pathlib import Path
import os
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
            bin_dir = root / "bin"
            bin_dir.mkdir()
            docker = bin_dir / "docker"
            docker.write_text("#!/usr/bin/env bash\nexit 0\n")
            docker.chmod(0o755)
            environment = os.environ | {"PATH": f"{bin_dir}:{os.environ['PATH']}"}
            for image in (
                "ghcr.io/metronforge/affine-bundle-solver-texlive:latest",
                "ghcr.io/metronforge/affine-bundle-solver-texlive@sha256:bad",
                "ghcr.io/metronforge/affine-bundle-solver-texlive@sha256:a0e7a52816065017954a0b3df24f5d8dade299f2ddf452d9e766c07863e1834b",
                "",
            ):
                with self.subTest(image=image):
                    (root / "ci/texlive/image.txt").write_text(image + "\n")
                    result = subprocess.run(["bash", str(target)], text=True,
                                            capture_output=True, env=environment, timeout=5)
                    self.assertEqual(2, result.returncode, result.stdout + result.stderr)
                    self.assertIn("invalid immutable TeX image reference", result.stderr)

    def test_image_declares_graphics_dependency_and_generic_command_entrypoint(self):
        dockerfile = (ROOT / "ci/texlive/Dockerfile").read_text()
        self.assertIn("texlive-pictures", dockerfile)
        self.assertIn("ENTRYPOINT [\"abs-tex-run\"]", dockerfile)
        self.assertIn("COPY run-command /usr/local/bin/abs-tex-run", dockerfile)

    def test_publisher_uses_explicit_shared_package_coordinate(self):
        workflow = (ROOT / ".github/workflows/texlive-image.yml").read_text()
        self.assertIn('image="ghcr.io/metronforge/texlive-custom"', workflow)
        self.assertNotIn('image="ghcr.io/${GITHUB_REPOSITORY,,}-texlive"', workflow)
        self.assertNotIn("pull_request:", workflow)

    def test_generic_command_is_forwarded_with_container_restrictions(self):
        launcher = ROOT / "scripts/build_manuscript_container.sh"
        with tempfile.TemporaryDirectory(prefix="abs-launcher-generic-") as temporary:
            root = Path(temporary)
            (root / "scripts").mkdir()
            (root / "ci/texlive").mkdir(parents=True)
            target = root / "scripts/build_manuscript_container.sh"
            shutil.copyfile(launcher, target)
            (root / "ci/texlive/image.txt").write_text(
                "ghcr.io/metronforge/texlive-custom@sha256:" + "a" * 64 + "\n"
            )
            workspace = root / "different-project"
            workspace.mkdir()
            (workspace / "analysis-report.tex").write_text("\\documentclass{article}\n")
            bin_dir = root / "bin"
            bin_dir.mkdir()
            args_file = root / "docker-args"
            docker = bin_dir / "docker"
            docker.write_text(
                "#!/usr/bin/env bash\nprintf '%s\\n' \"$@\" > \"$DOCKER_ARGS_FILE\"\n"
            )
            docker.chmod(0o755)
            environment = os.environ | {
                "PATH": f"{bin_dir}:{os.environ['PATH']}",
                "DOCKER_ARGS_FILE": str(args_file),
            }
            result = subprocess.run(
                ["bash", str(target), str(workspace), "--", "pdflatex", "-halt-on-error", "analysis-report.tex"],
                text=True, capture_output=True, env=environment, timeout=5,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            args = args_file.read_text().splitlines()
            self.assertEqual(["pdflatex", "-halt-on-error", "analysis-report.tex"], args[-3:])
            for required in (
                "--network=none", "--read-only", "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
            ):
                self.assertIn(required, args)
            user_index = args.index("--user")
            self.assertEqual(f"{os.getuid()}:{os.getgid()}", args[user_index + 1])

            result = subprocess.run(
                ["bash", str(target), str(workspace)],
                text=True, capture_output=True, env=environment, timeout=5,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual("abs-build-manuscript", args_file.read_text().splitlines()[-1])


if __name__ == "__main__":
    unittest.main()
