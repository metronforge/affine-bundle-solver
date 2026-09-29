#!/usr/bin/env python3
"""Identify Git sources or a manifested source release without inventing a commit."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


def source_identity(root):
    root = Path(root).resolve()
    def git(*args):
        return subprocess.run(['git', *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()
    try:
        top = Path(git('rev-parse', '--show-toplevel')).resolve()
    except subprocess.CalledProcessError:
        top = None
    if top == root:
        return git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}'), bool(git('status', '--porcelain'))
    info = json.loads((root / 'SOURCE-PROVENANCE.json').read_text())
    commit, tree = info.get('source_commit', ''), info.get('source_tree', '')
    if not all(re.fullmatch('[0-9a-f]{40}', value) for value in (commit, tree)):
        raise ValueError('source archive lacks valid commit/tree provenance')
    entries = {}
    for line in (root / 'MANIFEST.sha256').read_text().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  \./(.+)', line)
        if not match:
            raise ValueError('invalid source manifest entry')
        digest, name = match.groups()
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or str(path) != name or name in entries:
            raise ValueError('unsafe or duplicate source manifest entry')
        entries[name] = digest
    if 'SOURCE-PROVENANCE.json' not in entries:
        raise ValueError('source provenance is not covered by manifest')
    dirty = False
    for name, expected in entries.items():
        path = root / name
        if not path.is_file() or path.is_symlink():
            dirty = True
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            dirty = True
    return commit, tree, dirty


if __name__ == '__main__':
    commit, tree, dirty = source_identity(Path.cwd())
    print(commit, tree, str(dirty).lower())
