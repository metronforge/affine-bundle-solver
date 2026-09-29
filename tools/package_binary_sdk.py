#!/usr/bin/env python3
"""CMake-installed qualification SDKs, never release/version artifacts."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import subprocess
import tarfile

from inspect_binary_sdk import audit, FLOORS

ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"router.h", "certified_api.h", "status_certificate.h", "stream.h", "operational_policy.h"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def verify_files(prefix):
    listed = {}
    for line in (prefix / "SHA256SUMS.txt").read_text().splitlines():
        digest, name = line.split("  ", 1)
        if name in listed or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
            raise ValueError("unsafe/duplicate checksum path")
        listed[name] = digest
    actual = {str(p.relative_to(prefix)) for p in prefix.rglob("*") if p.is_file()
              and p.name != "SHA256SUMS.txt"}
    if actual != set(listed):
        raise ValueError("checksum inventory mismatch")
    for name, digest in listed.items():
        if sha256(prefix / name) != digest:
            raise ValueError(f"checksum mismatch: {name}")


def extract_verified(archive, destination):
    archive, destination = Path(archive), Path(destination)
    expected = Path(str(archive) + ".sha256").read_text().strip()
    if expected != f"{sha256(archive)}  {archive.name}":
        raise ValueError("archive checksum mismatch")
    with tarfile.open(archive, "r:gz") as tar:
        roots = set()
        for member in tar.getmembers():
            p = PurePosixPath(member.name)
            if p.is_absolute() or ".." in p.parts or not p.parts or not (member.isdir() or member.isfile()):
                raise ValueError(f"unsafe archive member: {member.name}")
            roots.add(p.parts[0])
        if len(roots) != 1:
            raise ValueError("archive must have one SDK root")
        destination.mkdir(parents=True, exist_ok=False)
        tar.extractall(destination, filter="data")
    prefix = destination / roots.pop()
    verify_files(prefix)
    return prefix


def package(build, output, target):
    build, output = Path(build).resolve(), Path(output).resolve()
    if command("git", "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("qualification requires a clean committed source tree")
    commit = command("git", "rev-parse", "HEAD")
    actual = ("macos" if platform.system() == "Darwin" else "linux") + "-" + (
        "arm64" if platform.machine() in ("arm64", "aarch64") else platform.machine())
    if actual != target:
        raise ValueError(f"native build required: {actual} != {target}")
    cache = {}
    for line in (build / "CMakeCache.txt").read_text().splitlines():
        if not line.startswith(("#", "//")) and ":" in line and "=" in line:
            key, value = line.split("=", 1); cache[key.split(":")[0]] = value
    if cache.get("ABS_ARCH_FLAGS") != "" or cache.get("ABS_BLAS") != "system":
        raise ValueError("qualification requires empty arch flags and system LP64 provider")
    if any(x in (build / "compile_commands.json").read_text() for x in ("-march=native", "-mcpu=native")):
        raise ValueError("native tuning is prohibited")
    name = f"affine-bundle-solver-qual-{commit[:12]}-{target}"
    prefix = output / "stage" / name
    if prefix.exists():
        raise ValueError("staging prefix must be fresh")
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cmake", "--install", str(build), "--prefix", str(prefix)], check=True)
    if {p.name for p in (prefix / "include/affine_bundle").iterdir()} != HEADERS:
        raise ValueError("installed public-header inventory differs from SDK contract")
    for name_ in ("LICENSE", "NOTICE"):
        shutil.copy2(ROOT / name_, prefix / name_)
    compiler = cache["CMAKE_C_COMPILER"]
    if target == "macos-arm64":
        blas = command("brew", "list", "--versions", "openblas")
        omp = command("brew", "list", "--versions", "libomp")
        os_name, libc = command("sw_vers"), None
        dependencies = "Install with `brew install openblas libomp`. External LP64 libraries must be at " \
            "`/opt/homebrew/opt/openblas/lib/libopenblas.0.dylib` and " \
            "`/opt/homebrew/opt/libomp/lib/libomp.dylib`. These absolute Homebrew install names are intentional."
    else:
        blas = command("dpkg-query", "-W", "-f=${Package} ${Version}\\n", "libblas3", "liblapack3")
        omp = command("dpkg-query", "-W", "-f=${Package} ${Version}", "libgomp1")
        os_name, libc = Path("/etc/os-release").read_text(), command("getconf", "GNU_LIBC_VERSION")
        dependencies = "Install with `sudo apt-get install libblas3 liblapack3 libgomp1`. " \
            "LP64 reference BLAS/LAPACK is qualified; libgfortran/libquadmath/libgcc dependencies " \
            "are resolved by the package manager. No BLAS or OpenMP runtime is bundled."
    info = dict(repository="metronforge/affine-bundle-solver", source_commit=commit,
                source_tree=command("git", "rev-parse", "HEAD^{tree}"), source_dirty=False,
                platform=target, architecture=platform.machine(), os=os_name,
                compiler=Path(compiler).name, compiler_version=command(compiler, "--version"),
                libc=libc, cpu_baseline="x86-64 baseline" if target == "linux-x86_64" else "ARMv8-A",
                blas_provider="OpenBLAS LP64" if target == "macos-arm64" else "reference BLAS/LAPACK LP64",
                blas_version=blas, openmp_runtime=omp, cmake_version=command("cmake", "--version"),
                build_options={"ABS_ARCH_FLAGS": "", "ABS_BLAS": "system"},
                deployment_target=cache.get("CMAKE_OSX_DEPLOYMENT_TARGET"),
                tested_userspace_floor=FLOORS.get(target, "macOS 15"),
                build_command="cmake --build <build> --parallel 3; cmake --install <build> --prefix <SDK>")
    (prefix / "DEPENDENCIES.md").write_text("# External runtime contract\n\n" + dependencies +
        "\n\nOwn libraries use relative loader paths. This is a qualification SDK, not a released version.\n")
    inspection = audit(prefix, target, (ROOT, build, prefix, output))
    info["libraries"] = [{k: r[k] for k in ("path", "sha256", "needed")} for r in inspection["libraries"]]
    (prefix / "BUILD-INFO.json").write_text(json.dumps(info, indent=2) + "\n")
    audit(prefix, target, (ROOT, build, prefix, output))
    (output / "inspection.json").write_text(json.dumps(inspection, indent=2) + "\n")
    shutil.copy2(prefix / "BUILD-INFO.json", output / "BUILD-INFO.json")
    (prefix / "SHA256SUMS.txt").write_text("".join(
        f"{sha256(p)}  {p.relative_to(prefix)}\n" for p in sorted(prefix.rglob("*")) if p.is_file()))
    verify_files(prefix)
    archive = output / (name + ".tar.gz")
    timestamp = int(command("git", "show", "-s", "--format=%ct", "HEAD"))
    def normalize(member):
        member.uid = member.gid = 0; member.uname = member.gname = ""
        member.mtime = timestamp
        return member
    with archive.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=timestamp) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            tar.add(prefix, arcname=name, filter=normalize)
    Path(str(archive) + ".sha256").write_text(f"{sha256(archive)}  {archive.name}\n")
    print(archive)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("package"); p.add_argument("build"); p.add_argument("output"); p.add_argument("target")
    p = sub.add_parser("extract"); p.add_argument("archive"); p.add_argument("destination")
    args = parser.parse_args()
    if args.action == "package":
        package(args.build, args.output, args.target)
    else:
        print(extract_verified(args.archive, args.destination))
