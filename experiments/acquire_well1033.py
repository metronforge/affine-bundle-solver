#!/usr/bin/env python3
"""Acquire the public Harwell--Boeing WELL1033 MatrixMarket matrix and RHS.

The release already bundles checksummed copies under data/.  This script exists
so the external source can be reacquired independently.  It downloads the NIST
Matrix Market gzip files, decompresses them, and verifies the bytes against the
release checksums.
"""
from pathlib import Path
import gzip, hashlib, urllib.request

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
FILES = {
    "well1033.mtx": (
        "https://math.nist.gov/pub/MatrixMarket2/Harwell-Boeing/lsq/well1033.mtx.gz",
        "9953cb6091a268afb6725bd92c26cdea68c8897b2d9a31a0656b0c0022e25f0c",
    ),
    "well1033_rhs1.mtx": (
        "https://math.nist.gov/pub/MatrixMarket2/Harwell-Boeing/lsq/well1033_rhs1.mtx.gz",
        "2a9e1c688987c63facdd646cdc8441c447ea5d708de38c8ccdec9fcb91007e31",
    ),
}
for name, (url, expected) in FILES.items():
    raw = urllib.request.urlopen(url, timeout=60).read()
    data = gzip.decompress(raw)
    got = hashlib.sha256(data).hexdigest()
    if got != expected:
        raise SystemExit(f"checksum mismatch for {name}: {got} != {expected}")
    (DATA / name).write_bytes(data)
    print(f"{name}: {got} OK")
