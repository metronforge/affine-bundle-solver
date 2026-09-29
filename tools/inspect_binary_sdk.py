#!/usr/bin/env python3
"""Structural qualification of installed SDKs; ldd alone is not an ABI audit."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

STEMS = ("affine_bundle_solver", "certified_solver", "status_verifier")
FLOORS = {"linux-x86_64": "2.35", "linux-arm64": "2.39"}


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)


def version(value):
    return tuple(map(int, value.split(".")))


def check_elf(header, dynamic, versions, name, target):
    machine = {"linux-x86_64": "Advanced Micro Devices X86-64", "linux-arm64": "AArch64"}[target]
    if not re.search(r"Machine:\s*" + re.escape(machine) + r"\s*$", header, re.M):
        raise ValueError("wrong ELF machine")
    sonames = re.findall(r"\(SONAME\).*?\[([^]]+)\]", dynamic)
    needed = re.findall(r"\(NEEDED\).*?\[([^]]+)\]", dynamic)
    paths = re.findall(r"\((?:RUNPATH|RPATH)\).*?\[([^]]+)\]", dynamic)
    if sonames != [name] or not needed or paths != ["$ORIGIN"]:
        raise ValueError(f"invalid SONAME/needed/relative runtime path: {sonames}, {needed}, {paths}")
    if any("/" in n for n in needed) or "GLIBCXX_" in versions:
        raise ValueError("unexpected absolute or C++ dependency")
    glibc = sorted(set(re.findall(r"\bGLIBC_([0-9]+\.[0-9.]+)", versions)), key=version)
    if not glibc or version(glibc[-1]) > version(FLOORS[target]):
        raise ValueError(f"glibc requirements {glibc} exceed or do not establish {FLOORS[target]}")
    return dict(machine=machine, soname=sonames[0], needed=needed, runtime_paths=paths,
                glibc_versions=glibc, highest_glibc=glibc[-1], glibcxx_versions=[])


def check_macho(arch, identity, loads, paths, deployment, name):
    own = {f"lib{s}.dylib" for s in STEMS}
    if arch.strip() != "arm64" or identity != "@rpath/" + name:
        raise ValueError("wrong Mach-O architecture or install identity")
    if not paths or any(p != "@loader_path" for p in paths):
        raise ValueError(f"nonrelocatable Mach-O rpaths: {paths}")
    if version(deployment) != (15, 0):
        raise ValueError(f"unexpected deployment target: {deployment}")
    external = {"/usr/lib/libSystem.B.dylib", "/opt/homebrew/opt/libomp/lib/libomp.dylib",
                "/opt/homebrew/opt/openblas/lib/libopenblas.0.dylib"}
    for load in loads:
        if load in external or load in {"@rpath/" + n for n in own}:
            continue
        raise ValueError(f"unqualified Mach-O dependency: {load}")
    return dict(architecture=arch.strip(), install_name=identity, needed=loads,
                runtime_paths=paths, deployment_target=deployment)


def audit(prefix, target, forbidden=()):
    prefix = Path(prefix).resolve()
    suffix = ".dylib" if target == "macos-arm64" else ".so"
    expected = {f"lib{s}{suffix}" for s in STEMS}
    actual = {p.name for p in (prefix / "lib").iterdir() if p.is_file()}
    if actual != expected:
        raise ValueError(f"unexpected library inventory: {actual}")
    # Inspect every installed file, not just dynamic load commands. Metadata
    # generated later must likewise contain no machine-specific build paths.
    for p in prefix.rglob("*"):
        if p.is_symlink():
            raise ValueError(f"unexpected SDK symlink: {p}")
        if p.is_file():
            data = p.read_bytes()
            for value in forbidden:
                if value and str(value).encode() in data:
                    raise ValueError(f"embedded forbidden path {value} in {p.relative_to(prefix)}")
    records = []
    for name in sorted(expected):
        p = prefix / "lib" / name
        raw = {"file": run("file", str(p))}
        if target == "macos-arm64":
            raw.update(otool_L=run("otool", "-L", str(p)), otool_l=run("otool", "-l", str(p)))
            identity = run("otool", "-D", str(p)).splitlines()[1].strip()
            loads = [s.strip().split(" (", 1)[0] for s in raw["otool_L"].splitlines()[1:]]
            loads.remove(identity)
            paths = re.findall(r"cmd LC_RPATH\s+cmdsize \d+\s+path (.*?) \(offset", raw["otool_l"])
            match = re.search(r"cmd LC_BUILD_VERSION.*?\bminos ([0-9.]+)", raw["otool_l"], re.S)
            if not match:
                raise ValueError("missing Mach-O deployment command")
            fields = check_macho(run("lipo", "-archs", str(p)), identity, loads, paths, match[1], name)
        else:
            raw.update(header=run("readelf", "-h", str(p)), dynamic=run("readelf", "-d", str(p)),
                       versions=run("readelf", "--version-info", str(p)), notes=run("readelf", "-n", str(p)),
                       resolution=run("ldd", str(p)))
            if "not found" in raw["resolution"]:
                raise ValueError(raw["resolution"])
            fields = check_elf(raw["header"], raw["dynamic"], raw["versions"], name, target)
            for needed, path in re.findall(r"(\S+) => (/\S+)", raw["resolution"]):
                if needed in expected and Path(path).resolve().parent != prefix / "lib":
                    raise ValueError(f"own dependency escaped SDK: {needed} => {path}")
            if target == "linux-x86_64":
                disassembly = run("objdump", "-d", "--no-show-raw-insn", str(p))
                if re.search(r"^\s*[0-9a-f]+:\s+v[a-z0-9]+\b", disassembly, re.M):
                    raise ValueError("VEX/AVX instruction in baseline x86 solver")
                fields["x86_vex_avx_instruction_count"] = 0
        records.append(dict(path="lib/" + name, sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                            **fields, inspection=raw))
    router = next(r for r in records if "libaffine_bundle_solver" in r["path"])
    if not any("blas" in n for n in router["needed"]) or not any("omp" in n for n in router["needed"]):
        raise ValueError("BLAS and OpenMP must remain external dynamic dependencies")
    return {"platform": target, "libraries": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("prefix"); parser.add_argument("target")
    parser.add_argument("--forbid", action="append", default=[])
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(args.prefix, args.target, args.forbid), indent=2) + "\n")
