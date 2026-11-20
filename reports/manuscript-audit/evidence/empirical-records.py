"""Recompute laptop and development claims locally; no timings are replayed."""
import csv
import hashlib
import io
import json
import math
import statistics
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
MAIN = '1df77461faf407320dab200d025fa846b2151502'
SOLVE = '361f068d9fa10b603e99ca12ccce6afe35784d90'
CERT = '1df7ec9048f92585cf95ef01a6b2fa2ffc1fac5a'


def read(commit, path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{commit}:{path}'])


def laptop():
    csv_path = 'results/synthetic-reference.csv'
    csv_bytes = read(MAIN, csv_path)
    for line in read(MAIN, 'results/synthetic-reference.sha256').decode().splitlines():
        digest, filename = line.split()
        assert hashlib.sha256(read(MAIN, 'results/' + filename)).hexdigest() == digest
    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode())))
    metadata = json.loads(read(MAIN, 'results/synthetic-reference.metadata.json'))
    assert len(rows) == len(metadata['results']) == 29
    print('case,method,status,rank,lo,hi,berr,router_ms,baseline_ms,router_MAD_ms,baseline_MAD_ms,ratio')
    for row, meta in zip(rows, metadata['results']):
        assert row['numerical_valid'] == 'True' and meta['numerical_valid']
        assert row['case_id'] == meta['case_id']
        values = []
        deviations = []
        for key in ('router', 'baseline'):
            samples = json.loads(row[key + '_timings_s'])
            assert len(samples) == 11 and samples == meta[key + '_timings_s']
            center = statistics.median(samples)
            mad = statistics.median(abs(v - center) for v in samples)
            assert center == float(row[key + '_s']) and mad == float(row[key + '_mad_s'])
            values.append(center)
            deviations.append(mad)
        ratio = values[1] / values[0]
        assert ratio == float(row['baseline_over_router'])
        fields = [row[k] for k in ('case_id','baseline_name','status','rank','rank_lo','rank_hi','berr')]
        print(','.join(fields + [f'{1e3*v:.6f}' for v in values + deviations] + [f'{ratio:.6f}']))


def paired(commit, folder, filename, names, bootstrap):
    path = 'reports/' + folder + '/data/' + filename
    raw = read(commit, path)
    print('\n', commit, path, hashlib.sha256(raw).hexdigest())
    blocks = json.loads(raw)['blocks']
    assert len(blocks) == 8
    idx = np.random.default_rng(42).integers(8, size=(bootstrap, 8))
    distributions, points = [], []
    for name in names:
        left, right = [], []
        for block in blocks:
            a, b = block['base'][name], block['new'][name]
            keys = ('result','hashes') if folder == 'cert-performance' else (
                'input','rhs','policy','status','certainty','rank','exact','x','check','berr')
            assert all(a[k] == b[k] for k in keys)
            assert len(a['ms']) == len(b['ms']) == 3
            left.append(statistics.median(a['ms']))
            right.append(statistics.median(b['ms']))
        a, b = np.array(left), np.array(right)
        ma, mb = np.median(a), np.median(b)
        dist = np.median(b[idx], axis=1) / np.median(a[idx], axis=1)
        distributions.append(dist)
        p = mb / ma
        points.append(p)
        mad = np.median(abs((b/a)-np.median(b/a)))
        print(name, 'BASE, FINAL ms; ratio; paired MAD; 95% block percentile',
              ma, mb, p, mad, np.quantile(dist, [.025, .975]).tolist())
    gm = statistics.geometric_mean(points)
    family_ci = np.quantile(np.exp(np.mean(np.log(distributions), axis=0)), [.025, .975])
    print('family GM, reduction %, 95% ratio interval', gm, 100*(1-gm), family_ci.tolist())


laptop()
paired(SOLVE, 'ralph-30', 'final.json', ['w1','w2','w3'], 4000)
paired(SOLVE, 'ralph-30', 'holdout.json', ['hold1','hold2'], 4000)
paired(CERT, 'cert-performance', 'final.json', ['t1','t2','t3'], 5000)
paired(CERT, 'cert-performance', 'holdout.json', ['th1','th2'], 5000)
