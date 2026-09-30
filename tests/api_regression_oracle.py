"""Exact mathematical oracles, independent of solver classifications."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from api_regression_corpus import FixtureCase, discover_cases, load_manifest


ORACLE_SCHEMA = "affine-bundle-solver-exact-oracles-v1"
PROOF_PRIME = 1_000_000_007


@dataclass(frozen=True)
class OracleResult:
    case_id: str
    exact_status: str
    rank_a: int
    rank_augmented: int
    method: str
    premises: tuple[str, ...]
    evidence: dict[str, Any]
    A_sha256: str
    b_sha256: str


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


def integer_row_scaling(array: np.ndarray) -> list[list[int]]:
    """Represent each binary64 row as proportional exact integers."""
    rows = []
    for row in array:
        ratios = [float(value).as_integer_ratio() for value in row]
        common_denominator = max(denominator for _, denominator in ratios)
        if any(common_denominator % denominator for _, denominator in ratios):
            raise ValueError("binary64 denominators were not nested powers of two")
        rows.append(
            [
                numerator * (common_denominator // denominator)
                for numerator, denominator in ratios
            ]
        )
    return rows


def modular_rank(rows: list[list[int]], prime: int = PROOF_PRIME) -> tuple[int, list[int]]:
    matrix = [[value % prime for value in row] for row in rows]
    m = len(matrix)
    n = len(matrix[0]) if m else 0
    rank = 0
    pivots = []
    for column in range(n):
        pivot_row = next(
            (row for row in range(rank, m) if matrix[row][column]), None
        )
        if pivot_row is None:
            continue
        matrix[rank], matrix[pivot_row] = matrix[pivot_row], matrix[rank]
        inverse = pow(matrix[rank][column], -1, prime)
        matrix[rank] = [(value * inverse) % prime for value in matrix[rank]]
        for row in range(rank + 1, m):
            factor = matrix[row][column]
            if factor:
                matrix[row] = [
                    (value - factor * pivot) % prime
                    for value, pivot in zip(matrix[row], matrix[rank])
                ]
        pivots.append(column)
        rank += 1
        if rank == m:
            break
    return rank, pivots


def bareiss_rank(rows: list[list[int]]) -> tuple[int, list[int]]:
    """Exact fraction-free elimination; returns rational rank and pivots."""
    matrix = [row[:] for row in rows]
    m = len(matrix)
    n = len(matrix[0]) if m else 0
    rank = 0
    previous_pivot = 1
    pivots = []
    for column in range(n):
        pivot_row = next(
            (row for row in range(rank, m) if matrix[row][column]), None
        )
        if pivot_row is None:
            continue
        matrix[rank], matrix[pivot_row] = matrix[pivot_row], matrix[rank]
        pivot = matrix[rank][column]
        for row in range(rank + 1, m):
            multiplier = matrix[row][column]
            for right in range(column + 1, n):
                numerator = (
                    matrix[row][right] * pivot
                    - multiplier * matrix[rank][right]
                )
                quotient, remainder = divmod(numerator, previous_pivot)
                if remainder:
                    raise ArithmeticError("non-exact Bareiss division")
                matrix[row][right] = quotient
            matrix[row][column] = 0
        previous_pivot = pivot
        pivots.append(column)
        rank += 1
        if rank == m:
            break
    return rank, pivots


def adjudicate(case: FixtureCase) -> OracleResult:
    m, n = case.A.shape
    augmented = np.column_stack((case.A, case.b))
    integer_a = integer_row_scaling(case.A)
    integer_augmented = integer_row_scaling(augmented)
    modular_a, pivots_a = modular_rank(integer_a)
    modular_augmented, pivots_augmented = modular_rank(integer_augmented)
    evidence: dict[str, Any] = {
        "prime": PROOF_PRIME,
        "modular_rank_A": modular_a,
        "modular_rank_augmented": modular_augmented,
        "modular_pivots_A": pivots_a,
        "modular_pivots_augmented": pivots_augmented,
    }
    methods = ["binary64_exact_integer_row_scaling", "modular_minor_witness"]

    if modular_a == min(m, n):
        rank_a = modular_a
    else:
        rank_a, exact_pivots_a = bareiss_rank(integer_a)
        evidence["bareiss_pivots_A"] = exact_pivots_a
        methods.append("fraction_free_Bareiss_A")

    if rank_a == m:
        # Full row rank means col(A)=Q^m, so every b is compatible.
        rank_augmented = rank_a
        methods.append("full_row_rank_compatibility")
    elif modular_augmented == rank_a + 1:
        # Adding one column raises rank by at most one; the modular lower
        # bound therefore meets the exact upper bound.
        rank_augmented = modular_augmented
        methods.append("augmented_rank_upper_bound_plus_modular_witness")
    elif rank_a == n and m == n:
        rank_augmented = rank_a
        methods.append("square_full_rank_compatibility")
    else:
        rank_augmented, exact_pivots_augmented = bareiss_rank(integer_augmented)
        evidence["bareiss_pivots_augmented"] = exact_pivots_augmented
        methods.append("fraction_free_Bareiss_augmented")

    if rank_a != rank_augmented:
        status = "INCONSISTENT"
    elif rank_a == n:
        status = "UNIQUE"
    else:
        status = "INFINITE"
    return OracleResult(
        case_id=case.case_id,
        exact_status=status,
        rank_a=rank_a,
        rank_augmented=rank_augmented,
        method=" + ".join(methods),
        premises=(
            "A and b are the exact rational values represented by stored binary64",
            "nonzero rank modulo a prime is a lower bound on rational rank",
            "Bareiss elimination is exact over row-scaled integers",
        ),
        evidence=evidence,
        A_sha256=case.metadata["A_bytes_sha256"],
        b_sha256=case.metadata["b_bytes_sha256"],
    )


def load_oracles(path: Path) -> dict[str, OracleResult]:
    payload = json.loads(path.read_text())
    if payload.get("schema") != ORACLE_SCHEMA:
        raise ValueError(f"unsupported oracle schema: {payload.get('schema')!r}")
    return {
        record["case_id"]: OracleResult(
            **{**record, "premises": tuple(record["premises"])}
        )
        for record in payload["cases"]
    }


def verify_semantic_layers(observation, oracle: OracleResult) -> list[CheckResult]:
    certificate = observation.certificate
    checks = [
        CheckResult(
            "exact_source_not_claimed_by_combined_api",
            observation.exact_source.status == "UNKNOWN"
            and observation.exact_source.verification == "NOT_VERIFIED",
            f"{observation.exact_source.status}/{observation.exact_source.verification}",
        ),
        CheckResult(
            "oracle_kept_separate_from_operational_status",
            True,
            f"exact={oracle.exact_status}, operational={observation.operational.status}",
        ),
    ]
    profiles = (
        (1, "unique", certificate.eta_unique),
        (2, "infinite", certificate.eta_infinite),
        (4, "inconsistent", certificate.eta_inconsistent),
    )
    for bit, name, eta in profiles:
        generator = getattr(certificate, f"{name}_generator_code")
        verifier = getattr(certificate, f"{name}_verifier_code")
        accepted = bool(certificate.nearby_status_mask & bit)
        checks.append(
            CheckResult(
                f"{name}_nearby_profile_consistent",
                accepted == (generator == 0 and verifier == 0 and math.isfinite(eta)),
                f"accepted={accepted}, generator={generator}, verifier={verifier}, eta={eta}",
            )
        )
    status_code = {"UNIQUE": 1, "INFINITE": 2, "INCONSISTENT": 3}.get(
        observation.operational.status
    )
    status_bit = {1: 1, 2: 2, 3: 4}.get(status_code, 0)
    expected_projection = (
        status_code if status_bit and certificate.nearby_status_mask & status_bit else 0
    )
    checks.append(
        CheckResult(
            "legacy_projection_matches_operational_selection",
            certificate.certified_status == expected_projection,
            f"actual={certificate.certified_status}, expected={expected_projection}",
        )
    )
    return checks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--write", type=Path, required=True)
    args = parser.parse_args()
    cases = discover_cases(args.fixture_root, load_manifest(args.fixture_root))
    payload = {
        "schema": ORACLE_SCHEMA,
        "claim_limit": "exact stored binary64 inputs only; no solver verdict is an oracle",
        "cases": [asdict(adjudicate(case)) for case in cases],
    }
    args.write.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"wrote={len(cases)}")


if __name__ == "__main__":
    main()
