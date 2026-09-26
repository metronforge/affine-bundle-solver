"""Generate the deterministic v3.4 SHA-256 artifact inventory."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "campaign-v3.4"


def main() -> None:
    generated = {"SHA256SUMS", ".gitignore", "fenv_cost", "native_trace.so",
                 "unique_verifier_probe"}
    files = [path for path in CAMPAIGN.rglob("*") if path.is_file()
             and path.name not in generated and "inputs" not in path.parts]
    files += sorted((ROOT / "task5v34").glob("*"))
    files += [ROOT / "tests/test_v34_diagnostics.py", ROOT / "tests/test_v34_performance.py"]
    rows = []
    for path in sorted({path for path in files if path.is_file()}):
        rows.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(ROOT)}")
    (CAMPAIGN / "SHA256SUMS").write_text("\n".join(rows) + "\n")


if __name__ == "__main__":
    main()
