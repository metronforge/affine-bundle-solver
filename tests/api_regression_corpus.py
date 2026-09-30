"""Strict discovery and provenance for the frozen API regression fixtures."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


SCHEMA = "affine-bundle-solver-api-regression-v1"
SOURCE_COMMIT = "ae9b662d7f5755418aa80f31ade1fffcbefebafd"
EXPECTED_IDS = tuple(
    [f"T8-{index:03d}" for index in range(1, 33)]
    + [f"T8-{index:03d}" for index in range(36, 40)]
)


class CorpusError(ValueError):
    """The fixture inventory or one of its inputs is not the frozen corpus."""


@dataclass(frozen=True)
class FixtureCase:
    case_id: str
    path: Path
    A: np.ndarray
    b: np.ndarray
    metadata: dict[str, Any]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_float64_sha256(array: np.ndarray) -> str:
    """Hash C-contiguous little-endian binary64 payload bytes."""
    value = np.asarray(array)
    if value.dtype != np.dtype(np.float64):
        raise CorpusError(f"expected binary64 array, got {value.dtype}")
    if not np.isfinite(value).all():
        raise CorpusError("canonical array must contain only finite values")
    payload = np.ascontiguousarray(value, dtype="<f8").tobytes(order="C")
    return hashlib.sha256(payload).hexdigest()


def load_manifest(root: Path) -> dict[str, Any]:
    path = root / "manifest.json"
    try:
        manifest = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusError(f"cannot load fixture manifest {path}: {error}") from error
    if manifest.get("schema") != SCHEMA:
        raise CorpusError(f"unsupported fixture manifest schema: {manifest.get('schema')!r}")
    return manifest


def _validate_arrays(case_id: str, A: np.ndarray, b: np.ndarray) -> None:
    if A.dtype != np.dtype(np.float64) or b.dtype != np.dtype(np.float64):
        raise CorpusError(f"{case_id}: A and b must be binary64")
    if A.ndim != 2:
        raise CorpusError(f"{case_id}: A must be two-dimensional")
    if b.shape != (A.shape[0],):
        raise CorpusError(f"{case_id}: b shape {b.shape} does not match A rows {A.shape[0]}")
    if not np.isfinite(A).all() or not np.isfinite(b).all():
        raise CorpusError(f"{case_id}: A and b must contain only finite values")


def discover_cases(root: Path, manifest: dict[str, Any]) -> list[FixtureCase]:
    entries = manifest.get("cases")
    if not isinstance(entries, list):
        raise CorpusError("manifest cases must be a list")
    ids = [entry.get("case_id") for entry in entries]
    duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    if duplicates:
        raise CorpusError(f"duplicate fixture ID(s): {', '.join(duplicates)}")
    expected_ids = set(EXPECTED_IDS)
    actual_ids = set(ids)
    if actual_ids != expected_ids:
        missing = sorted(expected_ids - actual_ids)
        extra = sorted(actual_ids - expected_ids)
        raise CorpusError(f"fixture ID mismatch; missing={missing}, extra={extra}")

    declared_paths = {entry["path"] for entry in entries}
    on_disk_paths = {
        str(path.relative_to(root)) for path in (root / "inputs").glob("T8-*.npz")
    }
    if declared_paths != on_disk_paths:
        missing_paths = sorted(declared_paths - on_disk_paths)
        extra_paths = sorted(on_disk_paths - declared_paths)
        missing_ids = [Path(path).stem for path in missing_paths]
        raise CorpusError(
            f"fixture file mismatch; missing={missing_ids or missing_paths}, extra={extra_paths}"
        )

    cases: list[FixtureCase] = []
    for entry in sorted(entries, key=lambda item: item["case_id"]):
        case_id = entry["case_id"]
        path = root / entry["path"]
        try:
            with np.load(path, allow_pickle=False) as payload:
                if set(payload.files) != {"A", "b"}:
                    raise CorpusError(f"{case_id}: NPZ must contain exactly A and b")
                A = np.array(payload["A"], copy=True)
                b = np.array(payload["b"], copy=True)
        except (OSError, ValueError) as error:
            if isinstance(error, CorpusError):
                raise
            raise CorpusError(f"{case_id}: cannot load NPZ: {error}") from error
        _validate_arrays(case_id, A, b)
        if list(A.shape) != entry["shape"]:
            raise CorpusError(f"{case_id}: shape {list(A.shape)} != {entry['shape']}")
        checks = {
            "NPZ": (sha256_file(path), entry["npz_sha256"]),
            "A": (canonical_float64_sha256(A), entry["A_bytes_sha256"]),
            "b": (canonical_float64_sha256(b), entry["b_bytes_sha256"]),
        }
        for label, (actual, expected) in checks.items():
            if actual != expected:
                raise CorpusError(f"{case_id}: {label} hash mismatch: {actual} != {expected}")
        cases.append(FixtureCase(case_id, path, A, b, dict(entry)))
    return cases


def _source_fields(case: dict[str, Any]) -> dict[str, Any]:
    case_id = case["case_id"]
    number = int(case_id.split("-")[1])
    if number <= 29:
        return {
            "source_category": "abs_apps_generated",
            "attribution": "abs_apps",
            "upstream": {
                "generator": "task8_cases.py",
                "construction": case["construction"],
                "parameters": case["parameters"],
            },
            "transformation": "deterministic construction stored as dense binary64 A,b",
        }
    if number <= 32:
        return {
            "source_category": "rasg_datasets",
            "attribution": "rasg_bsd_2",
            "upstream": case["parameters"],
            "transformation": (
                "selected UVFITS channel; fixed 4x4 small-field Fourier operator; "
                "BLOCK_REAL_IMAG_V1 realification; measured visibility RHS"
            ),
        }
    return {
        "source_category": "suitesparse_collection",
        "attribution": "suitesparse_cc_by_4",
        "upstream": case["parameters"],
        "transformation": "complete symmetric sparse matrix to dense binary64; controlled b=e0",
    }


def build_manifest(source_root: Path, fixture_root: Path) -> dict[str, Any]:
    cases_path = source_root / (
        "campaigns/affine-bundle-solver-1000/results/"
        "task8-targeted-expansion/cases.json"
    )
    source_cases = {
        case["case_id"]: case for case in json.loads(cases_path.read_text())["cases"]
    }
    entries = []
    for case_id in EXPECTED_IDS:
        case = source_cases[case_id]
        relative = Path("inputs") / f"{case_id}.npz"
        path = fixture_root / relative
        with np.load(path, allow_pickle=False) as payload:
            A, b = payload["A"], payload["b"]
        _validate_arrays(case_id, A, b)
        entry = {
            "case_id": case_id,
            "path": str(relative),
            "shape": list(A.shape),
            "npz_sha256": sha256_file(path),
            "A_bytes_sha256": canonical_float64_sha256(A),
            "b_bytes_sha256": canonical_float64_sha256(b),
            "abs_apps_A_sha256": case["A_sha256"],
            "abs_apps_b_sha256": case["b_sha256"],
            "source_path": (
                "campaigns/affine-bundle-solver-1000/results/"
                f"task8-targeted-expansion/inputs/{case_id}.npz"
            ),
            **_source_fields(case),
        }
        entries.append(entry)
    return {
        "schema": SCHEMA,
        "expected_case_count": 36,
        "expected_shape_partition": {"square": 26, "tall": 8, "wide": 2},
        "source": {
            "repository": "https://github.com/metronforge/abs-apps",
            "commit": SOURCE_COMMIT,
        },
        "cases": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-manifest-from", type=Path)
    parser.add_argument("--fixture-root", type=Path)
    args = parser.parse_args()
    if not args.build_manifest_from or not args.fixture_root:
        parser.error("--build-manifest-from and --fixture-root are required")
    manifest = build_manifest(args.build_manifest_from, args.fixture_root)
    print(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
