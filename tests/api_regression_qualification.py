"""Broader, separately scheduled qualification of the frozen 36-case corpus."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import resource
import shlex
import subprocess
import time
from typing import Any

from api_regression_binding import invoke_legacy, load_library
from api_regression_corpus import discover_cases, load_manifest, sha256_file
from api_regression_decisions import policy_variants
from api_regression_runner import call_combined


MODES = (
    "legacy_diagnostic",
    "combined_default",
    "combined_tight_compatibility",
    "combined_wide_rank_band",
    "combined_tight_quality",
)


def expected_invocations(unique_cases: int) -> int:
    return unique_cases * len(MODES)


@dataclass(frozen=True)
class QualificationSummary:
    schema: str
    unique_case_ids: tuple[str, ...]
    unique_case_count: int
    expected_invocations: int
    attempted_invocations: int
    completed_invocations: int
    skipped_invocations: int
    mode_counts: dict[str, int]
    mode_status_counts: dict[str, dict[str, int]]
    wall_seconds: float
    peak_rss_kib: int
    compiler: str
    blas: list[dict[str, Any]]
    thread_configuration: dict[str, str]
    solver_commit: str
    solver_source_commit: str
    abs_apps_source_commit: str
    binary_sha256: dict[str, str]

    def validate(self) -> None:
        if self.unique_case_count != 36 or len(set(self.unique_case_ids)) != 36:
            raise ValueError(f"unique case count/IDs invalid: {self.unique_case_count}")
        required = expected_invocations(self.unique_case_count)
        if self.expected_invocations != required:
            raise ValueError(
                f"expected invocation declaration {self.expected_invocations} != {required}"
            )
        if self.attempted_invocations != required or self.completed_invocations != required:
            raise ValueError(
                f"attempted/completed invocations {self.attempted_invocations}/"
                f"{self.completed_invocations} != {required}"
            )
        if self.skipped_invocations:
            raise ValueError(f"skipped invocations: {self.skipped_invocations}")
        if set(self.mode_counts) != set(MODES):
            raise ValueError(f"missing/extra qualification mode: {sorted(self.mode_counts)}")
        for mode in MODES:
            if self.mode_counts[mode] != self.unique_case_count:
                raise ValueError(f"mode {mode} completed {self.mode_counts[mode]} cases")
        if self.wall_seconds <= 0.0 or self.peak_rss_kib <= 0:
            raise ValueError("resource measurements are absent")
        if not self.solver_commit or not self.solver_source_commit or not self.binary_sha256:
            raise ValueError("source/binary identities are absent")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]):
        return cls(**{**payload, "unique_case_ids": tuple(payload["unique_case_ids"])})


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=repository, text=True
    ).strip()


def _compiler_identity() -> str:
    command = shlex.split(os.environ.get("CC", "cc")) + ["--version"]
    return subprocess.check_output(command, text=True).splitlines()[0]


def _blas_identity() -> list[dict[str, Any]]:
    try:
        from threadpoolctl import threadpool_info
    except ImportError:
        return [{"status": "threadpoolctl unavailable"}]
    keep = ("user_api", "internal_api", "prefix", "version", "num_threads")
    identities = []
    for item in threadpool_info():
        identity = {key: item.get(key) for key in keep}
        identity["library"] = Path(item["filepath"]).name if item.get("filepath") else None
        identities.append(identity)
    return identities


def qualify(fixture_root: Path, repository: Path) -> QualificationSummary:
    started = time.perf_counter()
    cases = discover_cases(fixture_root, load_manifest(fixture_root))
    library = load_library(repository)
    policies = policy_variants(library)
    counts = {mode: 0 for mode in MODES}
    statuses = {mode: Counter() for mode in MODES}
    attempted = completed = skipped = 0
    for case in cases:
        for mode in MODES:
            attempted += 1
            if mode == "legacy_diagnostic":
                code, result = invoke_legacy(library, case.A, case.b)
                status = str(int(result.router_meta[0]))
            else:
                policy_name = mode.removeprefix("combined_")
                observation = call_combined(
                    case, policies[policy_name], library=library
                )
                code = observation.return_code
                status = observation.operational.status
            if code not in (0, 2):
                raise RuntimeError(f"{case.case_id}/{mode}: return code {code}")
            completed += 1
            counts[mode] += 1
            statuses[mode][status] += 1
    binary_names = (
        "libaffine_bundle_solver.so", "libcertified_solver.so", "libstatus_verifier.so"
    )
    summary = QualificationSummary(
        schema="affine-bundle-solver-api-regression-qualification-v1",
        unique_case_ids=tuple(case.case_id for case in cases),
        unique_case_count=len(cases),
        expected_invocations=expected_invocations(len(cases)),
        attempted_invocations=attempted,
        completed_invocations=completed,
        skipped_invocations=skipped,
        mode_counts=counts,
        mode_status_counts={mode: dict(counter) for mode, counter in statuses.items()},
        wall_seconds=time.perf_counter() - started,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        compiler=_compiler_identity(),
        blas=_blas_identity(),
        thread_configuration={
            name: os.environ.get(name, "unset")
            for name in (
                "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "ABS_CERT_UNIQUE_THREADS",
                "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"
            )
        },
        solver_commit=_git(repository, "rev-parse", "HEAD"),
        solver_source_commit=_git(
            repository, "log", "-1", "--format=%H", "--", "src", "include"
        ),
        abs_apps_source_commit="ae9b662d7f5755418aa80f31ade1fffcbefebafd",
        binary_sha256={name: sha256_file(repository / name) for name in binary_names},
    )
    summary.validate()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-root", type=Path, default=Path(__file__).parent / "fixtures/api-regression")
    parser.add_argument("--expect-unique-cases", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    summary = qualify(args.fixture_root, repository)
    if summary.unique_case_count != args.expect_unique_cases:
        parser.error(
            f"expected {args.expect_unique_cases} unique cases, got {summary.unique_case_count}"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary.to_dict(), indent=2, sort_keys=True) + "\n")
    print(
        f"unique={summary.unique_case_count} expected={summary.expected_invocations} "
        f"attempted={summary.attempted_invocations} completed={summary.completed_invocations} "
        f"skipped={summary.skipped_invocations} wall={summary.wall_seconds:.6f}s "
        f"peak_rss={summary.peak_rss_kib}KiB"
    )


if __name__ == "__main__":
    main()
