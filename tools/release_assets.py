#!/usr/bin/env python3
"""Validate/promote release bytes; never compile or package archives.

The checksum order is source, research, linux-x86_64, linux-arm64, macos-arm64.
"""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile

TARGETS = ('linux-x86_64', 'linux-arm64', 'macos-arm64')


def candidate_required(current, previous, dry_run=False):
    return dry_run or bool(previous and current != previous)


def context(root, dry_run=False):
    root = Path(root)
    current = json.loads((root / '.release-please-manifest.json').read_text())['.']
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    validate_identity(root, current, commit, os.environ.get('GITHUB_SHA', ''))
    previous_file = subprocess.run(['git', 'show', 'HEAD^:.release-please-manifest.json'],
                                   cwd=root, text=True, capture_output=True)
    previous = json.loads(previous_file.stdout)['.'] if previous_file.returncode == 0 else ''
    build = candidate_required(current, previous, dry_run)
    print(f"build={str(build).lower()}")
    print(f"version={current}")


def archive_names(version):
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-.][0-9A-Za-z.-]+)?', version):
        raise ValueError('invalid release version')
    return [f'affine-bundle-solver-v{version}{suffix}.tar.gz'
            for suffix in ('', '-research', *(f'-{target}' for target in TARGETS))]


def validate_identity(root, version, commit, expected_sha):
    archive_names(version)
    if not re.fullmatch(r'[0-9a-f]{40}', commit) or commit != expected_sha:
        raise ValueError('source commit does not match expected CI SHA')
    root = Path(root)
    manifest = json.loads((root / '.release-please-manifest.json').read_text())['.']
    cmake = re.search(r'project\(affine-bundle-solver\s+VERSION\s+(\S+)',
                      (root / 'CMakeLists.txt').read_text())
    citation = re.search(r'^version:\s+(\S+)', (root / 'CITATION.cff').read_text(), re.M)
    if not cmake or not citation or {version, manifest, cmake[1], citation[1]} != {version}:
        raise ValueError('release versions disagree: manifest/CMake/CITATION/input')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(directory, names):
    directory = Path(directory)
    if not directory.is_dir() or {p.name for p in directory.iterdir()} != set(names):
        raise ValueError(f'asset inventory mismatch: {directory}')
    if any(not (directory / name).is_file() or (directory / name).is_symlink() for name in names):
        raise ValueError('asset inventory must contain only regular files')


def write_checksums(directory, names):
    directory = Path(directory)
    (directory / 'SHA256SUMS.txt').write_text(''.join(
        f'{digest(directory / name)}  {name}\n' for name in names))


def verify_checksums(directory, names, manifest='SHA256SUMS.txt'):
    directory = Path(directory)
    lines = (directory / manifest).read_text().splitlines()
    # Canonical entries enforce count, order, names, syntax, duplicates and hashes.
    expected = [f'{digest(directory / name)}  {name}' for name in names]
    if lines != expected:
        raise ValueError(f'checksum manifest mismatch: {directory / manifest}')


def verify_binary(path, version, commit, target):
    root = path.name.removesuffix('.tar.gz')
    with tarfile.open(path, 'r:gz') as archive:
        seen = set()
        info = None
        for member in archive:
            name = PurePosixPath(member.name)
            if (name.is_absolute() or '..' in name.parts or not name.parts
                    or str(name) != member.name or name.parts[0] != root or member.name in seen
                    or not (member.isfile() or member.isdir())):
                raise ValueError('unsafe or duplicate binary archive member')
            seen.add(member.name)
            if member.name == root + '/BUILD-INFO.json':
                if not member.isfile() or member.size > 1024 * 1024:
                    raise ValueError('invalid BUILD-INFO')
                info = json.load(archive.extractfile(member))
    expected = dict(repository='metronforge/affine-bundle-solver', version=version,
                    release_tag='v' + version, source_commit=commit, platform=target)
    if not isinstance(info, dict) or any(info.get(k) != v for k, v in expected.items()):
        raise ValueError(f'BUILD-INFO identity mismatch: {path.name}')


def verify_candidate(directory, version, commit):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('invalid source commit')
    directory = Path(directory)
    names = archive_names(version)
    inventory(directory, names + ['SHA256SUMS.txt'])
    verify_checksums(directory, names)
    for target, name in zip(TARGETS, names[2:]):
        verify_binary(directory / name, version, commit, target)


def release_lookup_state(response, tag, commit):
    """Classify a GitHub release lookup response without treating API errors as releases."""
    if not isinstance(response, dict):
        raise ValueError('release lookup response must be a JSON object')
    if response.get('message') == 'Not Found':
        return 'missing'
    if response.get('tag_name') != tag or not isinstance(response.get('id'), int):
        raise ValueError('release lookup returned an error or an unexpected release')
    if response.get('target_commitish') != commit:
        raise ValueError('existing release targets a different source commit')
    if response.get('immutable') is True:
        return 'immutable'
    if response.get('draft') is True:
        return 'draft'
    raise ValueError('existing release is published but not immutable')


def require_identical(candidate, existing):
    # Compare the bytes directly; a matching filename or remote checksum is insufficient.
    with Path(candidate).open('rb') as left, Path(existing).open('rb') as right:
        while True:
            a, b = left.read(1024 * 1024), right.read(1024 * 1024)
            if a != b:
                raise ValueError(f'existing asset has different bytes: {Path(existing).name}')
            if not a:
                return


def aggregate(source, sdks, output, version, commit):
    source, sdks, output = Path(source), Path(sdks), Path(output)
    names = archive_names(version)
    inventory(source, names[:2] + ['SHA256SUMS.txt'])
    verify_checksums(source, names[:2])
    if {p.name for p in sdks.iterdir()} != {'sdk-' + target for target in TARGETS}:
        raise ValueError('binary producer inventory mismatch')
    inputs = [source / name for name in names[:2]]
    for target, name in zip(TARGETS, names[2:]):
        folder = sdks / ('sdk-' + target)
        inventory(folder, [name, name + '.sha256'])
        verify_checksums(folder, [name], name + '.sha256')
        verify_binary(folder / name, version, commit, target)
        inputs.append(folder / name)
    output.mkdir(parents=True, exist_ok=False)
    for path in inputs:
        shutil.copyfile(path, output / path.name)
    write_checksums(output, names)
    verify_candidate(output, version, commit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('context'); p.add_argument('root'); p.add_argument('--dry-run', action='store_true')
    p = sub.add_parser('names'); p.add_argument('version')
    p = sub.add_parser('identity')
    for name in ('root', 'version', 'commit', 'expected_sha'):
        p.add_argument(name)
    p = sub.add_parser('verify')
    for name in ('directory', 'version', 'commit'):
        p.add_argument(name)
    p = sub.add_parser('aggregate')
    for name in ('source', 'sdks', 'output', 'version', 'commit'):
        p.add_argument(name)
    p = sub.add_parser('identical'); p.add_argument('candidate'); p.add_argument('existing')
    p = sub.add_parser('release-state')
    p.add_argument('response')
    p.add_argument('tag')
    p.add_argument('commit')
    args = vars(parser.parse_args())
    action = args.pop('action')
    if action == 'names':
        print('\n'.join(archive_names(args['version']) + ['SHA256SUMS.txt']))
    elif action == 'release-state':
        response = json.loads(Path(args['response']).read_text())
        print(release_lookup_state(response, args['tag'], args['commit']))
    else:
        {'context': context, 'identity': validate_identity, 'verify': verify_candidate,
         'aggregate': aggregate, 'identical': require_identical}[action](**args)


if __name__ == '__main__':
    main()
