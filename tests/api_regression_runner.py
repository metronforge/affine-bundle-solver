"""Execute and normalize the frozen current combined-API regression corpus."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import subprocess
from typing import Any

from api_regression_binding import PolicyValues, default_policy, invoke, load_library
from api_regression_corpus import EXPECTED_IDS, FixtureCase, discover_cases, load_manifest


SOLVER_SOURCE_COMMIT = "2741af01f0c0116347dbc81b21998f538690dcea"


STATUS = {1: "UNIQUE", 2: "INFINITE", 3: "INCONSISTENT", 4: "FAIL", 5: "UNDECIDABLE"}
CERTAINTY = {1: "DETERMINISTIC", 2: "RANDOMISED", 3: "NONE"}
EXACT_STATUS = {0: "UNKNOWN", 1: "UNIQUE", 2: "INFINITE", 3: "INCONSISTENT"}
VERIFICATION = {
    0: "NOT_VERIFIED",
    1: "EXACT_RATIONAL",
    2: "INTERVAL_PROOF",
    3: "ANALYTIC_PROOF",
    4: "EXTERNAL_PROOF",
}


@dataclass(frozen=True)
class OperationalObservation:
    status: str
    certainty: str
    rank: int
    rank_interval: tuple[int, int]
    relative_residual: float
    relative_reference_error: float
    backward_error: float
    fallback: int
    raw_class: str
    grey_distinct_count: int
    grey_total_events: int
    last_orth_eta: float
    core_rank_interval: tuple[int, int]
    core_qr_rank: int
    formation_guard_counters: tuple[int, int, int]


@dataclass(frozen=True)
class ExactSourceObservation:
    status: str
    verification: str


@dataclass(frozen=True)
class CertificateObservation:
    nearby_status_mask: int
    eta_unique: float
    eta_infinite: float
    eta_inconsistent: float
    certified_status: int
    eta_status: float
    generator_code: int
    verifier_code: int
    unique_generator_code: int
    unique_verifier_code: int
    infinite_generator_code: int
    infinite_verifier_code: int
    inconsistent_generator_code: int
    inconsistent_verifier_code: int


@dataclass(frozen=True)
class CombinedObservation:
    case_id: str
    input_shape: tuple[int, int]
    invocation_mode: str
    policy: tuple[float, float, float, float]
    return_code: int
    operational: OperationalObservation
    exact_source: ExactSourceObservation
    certificate: CertificateObservation
    solution_vector: str


@dataclass(frozen=True)
class RunSummary:
    discovered_ids: tuple[str, ...]
    attempted_ids: tuple[str, ...]
    completed_ids: tuple[str, ...]
    observations: tuple[CombinedObservation, ...]

    @property
    def discovered_count(self):
        return len(self.discovered_ids)

    @property
    def attempted_count(self):
        return len(self.attempted_ids)

    @property
    def completed_count(self):
        return len(self.completed_ids)


def compare_value(actual: Any, expected: Any) -> bool:
    if isinstance(actual, float) and math.isnan(actual):
        return isinstance(expected, float) and math.isnan(expected)
    if isinstance(expected, float) and math.isnan(expected):
        return False
    return actual == expected


def snapshot_observation(observation: CombinedObservation) -> dict[str, Any]:
    return _json_value(asdict(observation))


def _assert_snapshot(actual: Any, expected: Any, path: str = "observation") -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise AssertionError(f"{path}: field set differs")
        for key in expected:
            _assert_snapshot(actual[key], expected[key], f"{path}.{key}")
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise AssertionError(f"{path}: sequence shape differs")
        for index, value in enumerate(expected):
            _assert_snapshot(actual[index], value, f"{path}[{index}]")
        return
    if isinstance(expected, float):
        if not isinstance(actual, (int, float)) or not math.isclose(
            float(actual), expected, rel_tol=1e-10, abs_tol=1e-15
        ):
            raise AssertionError(f"{path}: {actual!r} != {expected!r} within tolerance")
        return
    if actual != expected:
        raise AssertionError(f"{path}: {actual!r} != {expected!r}")


def call_combined(
    case: FixtureCase,
    policy: PolicyValues,
    mode: str = "combined_policy_v1",
    *,
    library=None,
) -> CombinedObservation:
    if mode != "combined_policy_v1":
        raise ValueError(f"unsupported invocation mode: {mode}")
    library = library or load_library()
    code, result = invoke(library, case.A, case.b, policy)
    op = result.operational
    meta = op.router_meta
    cert = result.certificate_profile
    return CombinedObservation(
        case_id=case.case_id,
        input_shape=tuple(case.A.shape),
        invocation_mode=mode,
        policy=policy.values(),
        return_code=code,
        operational=OperationalObservation(
            status=STATUS.get(op.operational_status, f"UNKNOWN_{op.operational_status}"),
            certainty=CERTAINTY.get(op.operational_certainty, f"UNKNOWN_{op.operational_certainty}"),
            rank=int(meta[2]),
            rank_interval=(int(meta[3]), int(meta[4])),
            relative_residual=float(meta[5]),
            relative_reference_error=float(meta[6]),
            backward_error=float(meta[10]),
            fallback=int(meta[8]),
            raw_class=STATUS.get(int(meta[9]), f"UNKNOWN_{int(meta[9])}"),
            grey_distinct_count=op.grey_distinct_count,
            grey_total_events=op.grey_total_events,
            last_orth_eta=op.last_orth_eta,
            core_rank_interval=tuple(op.core_rank_interval),
            core_qr_rank=op.core_qr_rank,
            formation_guard_counters=tuple(op.formation_guard_counters),
        ),
        exact_source=ExactSourceObservation(
            EXACT_STATUS.get(op.exact_source_status, f"UNKNOWN_{op.exact_source_status}"),
            VERIFICATION.get(
                op.exact_source_verification, f"UNKNOWN_{op.exact_source_verification}"
            ),
        ),
        certificate=CertificateObservation(
            nearby_status_mask=result.nearby_status_mask,
            eta_unique=result.eta_unique,
            eta_infinite=result.eta_infinite,
            eta_inconsistent=result.eta_inconsistent,
            certified_status=cert.certified_status,
            eta_status=cert.eta_status,
            generator_code=cert.generator_code,
            verifier_code=cert.verifier_code,
            unique_generator_code=cert.unique_generator_code,
            unique_verifier_code=cert.unique_verifier_code,
            infinite_generator_code=cert.infinite_generator_code,
            infinite_verifier_code=cert.infinite_verifier_code,
            inconsistent_generator_code=cert.inconsistent_generator_code,
            inconsistent_verifier_code=cert.inconsistent_verifier_code,
        ),
        solution_vector="not_exposed_by_current_api",
    )


def run_corpus(
    root: Path,
    *,
    library=None,
    include_ids: set[str] | None = None,
    verify_behavior: bool = False,
) -> RunSummary:
    library = library or load_library()
    cases = discover_cases(root, load_manifest(root))
    discovered = tuple(case.case_id for case in cases)
    selected = [case for case in cases if include_ids is None or case.case_id in include_ids]
    attempted: list[str] = []
    completed: list[str] = []
    observations = []
    for case in selected:
        attempted.append(case.case_id)
        observation = call_combined(case, default_policy(library), library=library)
        if observation.return_code not in (0, 2):
            raise RuntimeError(f"{case.case_id}: API return code {observation.return_code}")
        expected = case.metadata.get("current_api_behavior")
        if verify_behavior and expected is not None:
            _assert_snapshot(snapshot_observation(observation), expected, case.case_id)
        observations.append(observation)
        completed.append(case.case_id)
    expected = set(EXPECTED_IDS)
    completed_set = set(completed)
    if set(discovered) != expected or completed_set != expected:
        raise ValueError(
            f"incomplete run: missing={sorted(expected-completed_set)}, "
            f"extra={sorted(completed_set-expected)}"
        )
    return RunSummary(discovered, tuple(attempted), tuple(completed), tuple(observations))


def record_expectations(root: Path, *, library=None) -> None:
    manifest = load_manifest(root)
    if manifest["source"]["commit"] != "ae9b662d7f5755418aa80f31ade1fffcbefebafd":
        raise RuntimeError("refusing to record against an unexpected abs-apps revision")
    repository = Path(__file__).resolve().parents[1]
    if subprocess.run(
        ["git", "status", "--porcelain"], cwd=repository, text=True, capture_output=True, check=True
    ).stdout:
        raise RuntimeError("refusing to record from a dirty worktree")
    source_diff = subprocess.run(
        ["git", "diff", "--quiet", SOLVER_SOURCE_COMMIT, "--", "src", "include"],
        cwd=repository,
    )
    if source_diff.returncode:
        raise RuntimeError("refusing to record after solver source/API changes")
    summary = run_corpus(root, library=library)
    snapshots = {item.case_id: snapshot_observation(item) for item in summary.observations}
    for entry in manifest["cases"]:
        entry["current_api_behavior"] = snapshots[entry["case_id"]]
    manifest["behavior_contract"] = {
        "solver_source_commit": SOLVER_SOURCE_COMMIT,
        "classification": {
            "input_shape": "invariant",
            "invocation_mode": "invariant",
            "policy": "invariant",
            "return_code": "behavior",
            "operational": "behavior",
            "exact_source": "behavior_not_mathematical_oracle",
            "certificate": "behavior_nearby_system_guarantees_only",
            "solution_vector": "invariant_not_exposed",
            "elapsed_time": "dont_care_not_recorded",
        },
        "float_tolerance": {"relative": 1e-10, "absolute": 1e-15},
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )


def _json_value(value):
    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            return "semantic_absence:NaN"
        return "no_finite_bound:+Infinity" if value > 0 else "no_finite_bound:-Infinity"
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-root", type=Path, default=Path(__file__).parent / "fixtures/api-regression")
    parser.add_argument("--expect-count", type=int, required=True)
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    if args.record:
        record_expectations(args.fixture_root)
        print(f"recorded={args.expect_count}")
        return
    summary = run_corpus(args.fixture_root, verify_behavior=True)
    if summary.completed_count != args.expect_count:
        raise SystemExit(f"expected {args.expect_count}, completed {summary.completed_count}")
    print(json.dumps(_json_value(asdict(summary)), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
