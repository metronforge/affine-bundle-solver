"""Release promotion contract, using deterministic archives and no GitHub writes."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import release_assets as release

VERSION = '1.2.3'
SHA = 'a' * 40


def binary(path, target, **overrides):
    info = dict(repository='metronforge/affine-bundle-solver', version=VERSION,
                release_tag='v' + VERSION, source_commit=SHA, platform=target)
    info.update(overrides)
    with tarfile.open(path, 'w:gz') as archive:
        data = json.dumps(info).encode()
        member = tarfile.TarInfo(path.name.removesuffix('.tar.gz') + '/BUILD-INFO.json')
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))


class ReleaseContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.candidate = self.root / 'candidate'
        self.candidate.mkdir()
        self.names = release.archive_names(VERSION)
        for name in self.names[:2]:
            (self.candidate / name).write_bytes(b'source/research fixture')
        for target, name in zip(release.TARGETS, self.names[2:]):
            binary(self.candidate / name, target)
        release.write_checksums(self.candidate, self.names)

    def test_ordinary_commit_and_dry_run_detection(self):
        self.assertFalse(release.candidate_required('1.2.3', '1.2.3', False))
        self.assertFalse(release.candidate_required('1.2.3', '', False))
        self.assertTrue(release.candidate_required('1.2.3', '1.2.2', False))
        self.assertTrue(release.candidate_required('1.2.3', '1.2.3', True))

    def test_names_and_five_entry_order(self):
        self.assertEqual(self.names, [f'affine-bundle-solver-v1.2.3{s}.tar.gz' for s in
                                     ('', '-research', '-linux-x86_64', '-linux-arm64', '-macos-arm64')])
        lines = (self.candidate / 'SHA256SUMS.txt').read_text().splitlines()
        self.assertEqual([line.split('  ')[1] for line in lines], self.names)
        release.verify_candidate(self.candidate, VERSION, SHA)

    def test_missing_binary_rejected(self):
        (self.candidate / self.names[3]).unlink()
        with self.assertRaisesRegex(ValueError, 'inventory'):
            release.verify_candidate(self.candidate, VERSION, SHA)

    def test_unexpected_asset_rejected(self):
        (self.candidate / 'extra').write_text('extra')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            release.verify_candidate(self.candidate, VERSION, SHA)

    def test_corruption_rejected(self):
        (self.candidate / self.names[0]).write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            release.verify_candidate(self.candidate, VERSION, SHA)

    def test_checksum_inventory_duplicate_and_unsafe_rejected(self):
        checksums = self.candidate / 'SHA256SUMS.txt'
        original = checksums.read_text()
        for bad in [original + original.splitlines()[0] + '\n',
                    original.replace(self.names[0], '../escape'), original.upper()]:
            checksums.write_text(bad)
            with self.assertRaises(ValueError):
                release.verify_candidate(self.candidate, VERSION, SHA)

    def test_build_info_identity_rejected_even_with_valid_outer_hash(self):
        for field, value in [('source_commit', 'b' * 40), ('version', '1.2.4'),
                             ('release_tag', 'v1.2.4'), ('platform', 'windows'),
                             ('repository', 'someone/else')]:
            binary(self.candidate / self.names[2], release.TARGETS[0], **{field: value})
            release.write_checksums(self.candidate, self.names)
            with self.assertRaisesRegex(ValueError, 'BUILD-INFO'):
                release.verify_candidate(self.candidate, VERSION, SHA)

    def test_existing_identical_asset(self):
        release.require_identical(self.candidate / self.names[0], self.candidate / self.names[1])

    def test_existing_different_asset_rejected(self):
        with self.assertRaisesRegex(ValueError, 'different bytes'):
            release.require_identical(self.candidate / self.names[0], self.candidate / self.names[2])

    def test_version_and_source_identity(self):
        (self.root / '.release-please-manifest.json').write_text(json.dumps({'.': VERSION}))
        (self.root / 'CMakeLists.txt').write_text('project(affine-bundle-solver\n VERSION 1.2.3\n LANGUAGES C)')
        (self.root / 'CITATION.cff').write_text('version: 1.2.3 # comment\n')
        release.validate_identity(self.root, VERSION, SHA, SHA)
        for version, commit, expected in [('1.2.4', SHA, SHA), (VERSION, SHA, 'b' * 40),
                                           (VERSION, SHA, ''), ('../bad', SHA, SHA)]:
            with self.assertRaises(ValueError):
                release.validate_identity(self.root, version, commit, expected)
        for file, text in [('CMakeLists.txt', 'project(affine-bundle-solver VERSION 1.2.4)'),
                           ('CITATION.cff', 'version: 1.2.4')]:
            original = (self.root / file).read_text()
            (self.root / file).write_text(text)
            with self.assertRaises(ValueError):
                release.validate_identity(self.root, VERSION, SHA, SHA)
            (self.root / file).write_text(original)

    def test_aggregate_preserves_exact_producer_bytes(self):
        source = self.root / 'source'
        source.mkdir()
        for name in self.names[:2]:
            (source / name).write_bytes((self.candidate / name).read_bytes())
        release.write_checksums(source, self.names[:2])
        sdk_root = self.root / 'sdks'
        for target, name in zip(release.TARGETS, self.names[2:]):
            folder = sdk_root / ('sdk-' + target)
            folder.mkdir(parents=True)
            data = (self.candidate / name).read_bytes()
            (folder / name).write_bytes(data)
            (folder / (name + '.sha256')).write_text(hashlib.sha256(data).hexdigest() + '  ' + name + '\n')
        output = self.root / 'aggregate'
        release.aggregate(source, sdk_root, output, VERSION, SHA)
        for name in self.names + ['SHA256SUMS.txt']:
            self.assertEqual((output / name).read_bytes(), (self.candidate / name).read_bytes())
        (sdk_root / 'sdk-linux-arm64' / self.names[3]).unlink()
        with self.assertRaises(ValueError):
            release.aggregate(source, sdk_root, self.root / 'missing', VERSION, SHA)


if __name__ == '__main__':
    unittest.main()
