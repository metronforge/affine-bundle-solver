"""Qualification must reject wrong ABI, leaked paths and corrupt archives."""
import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from inspect_binary_sdk import check_elf, check_macho
from package_binary_sdk import extract_verified, sha256


class AuditContract(unittest.TestCase):
    def test_elf_floor_and_loader_contract(self):
        hdr = "Machine: Advanced Micro Devices X86-64"
        dyn = "(SONAME) [libstatus_verifier.so]\n(NEEDED) [libc.so.6]\n(RUNPATH) [$ORIGIN]"
        r = check_elf(hdr, dyn, "GLIBC_2.9 GLIBC_2.17", "libstatus_verifier.so", "linux-x86_64")
        self.assertEqual(r["highest_glibc"], "2.17")
        for h, d, v in [(hdr, dyn, "GLIBC_2.36"), (hdr, dyn, "GLIBCXX_3.4"),
                        ("Machine: AArch64", dyn, "GLIBC_2.17"),
                        (hdr, dyn.replace("$ORIGIN", "/tmp/stage"), "GLIBC_2.17"),
                        (hdr, dyn.replace("(SONAME)", "other"), "GLIBC_2.17")]:
            with self.assertRaises(ValueError):
                check_elf(h, d, v, "libstatus_verifier.so", "linux-x86_64")

    def test_macho_own_and_external_names(self):
        loads = ["@rpath/libstatus_verifier.dylib", "/usr/lib/libSystem.B.dylib",
                 "/opt/homebrew/opt/libomp/lib/libomp.dylib"]
        check_macho("arm64", "@rpath/libstatus_verifier.dylib", loads,
                    ["@loader_path"], "15.0", "libstatus_verifier.dylib")
        for bad in ["/tmp/build/libstatus_verifier.dylib", "@rpath/libmystery.dylib"]:
            with self.assertRaises(ValueError):
                check_macho("arm64", "@rpath/libstatus_verifier.dylib", loads + [bad],
                            ["@loader_path"], "15.0", "libstatus_verifier.dylib")

    def test_archive_checksum_and_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "sdk.tar.gz"
            with tarfile.open(p, "w:gz") as t:
                data = b"untrusted"
                item = tarfile.TarInfo("../escape"); item.size = len(data)
                t.addfile(item, io.BytesIO(data))
            sidecar = Path(str(p) + ".sha256")
            sidecar.write_text("0" * 64 + "  sdk.tar.gz\n")
            with self.assertRaisesRegex(ValueError, "checksum"):
                extract_verified(p, Path(tmp) / "bad")
            sidecar.write_text(sha256(p) + "  sdk.tar.gz\n")
            with self.assertRaisesRegex(ValueError, "unsafe"):
                extract_verified(p, Path(tmp) / "bad")
            self.assertFalse((Path(tmp).parent / "escape").exists())


if __name__ == "__main__":
    unittest.main()
