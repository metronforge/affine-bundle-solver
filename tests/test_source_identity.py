"""Source archives retain truthful provenance without a Git checkout."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from source_identity import source_identity


class SourceIdentity(unittest.TestCase):
    def test_archive_identity_and_modified_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            provenance = root / 'SOURCE-PROVENANCE.json'
            provenance.write_text(json.dumps({'source_commit': 'a' * 40, 'source_tree': 'b' * 40}))
            (root / 'source.c').write_text('original source')
            manifest = ''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  ./{p.name}\n'
                               for p in sorted(root.iterdir()))
            (root / 'MANIFEST.sha256').write_text(manifest)
            self.assertEqual(source_identity(root), ('a' * 40, 'b' * 40, False))
            (root / 'source.c').write_text('modified source')
            self.assertEqual(source_identity(root), ('a' * 40, 'b' * 40, True))
            (root / 'source.c').unlink()
            self.assertTrue(source_identity(root)[2])
            provenance.write_text('{}')
            with self.assertRaises(ValueError):
                source_identity(root)

    def test_unknown_source_does_not_claim_clean_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises((ValueError, FileNotFoundError)):
                source_identity(Path(tmp))

    def test_repository_identity(self):
        root = Path(__file__).resolve().parents[1]
        commit, tree, dirty = source_identity(root)
        self.assertEqual(len(commit), 40)
        self.assertEqual(len(tree), 40)
        self.assertIsInstance(dirty, bool)


if __name__ == '__main__':
    unittest.main()
