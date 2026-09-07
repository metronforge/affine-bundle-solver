# Contributing

## Commit messages

This repository uses [Conventional Commits](https://www.conventionalcommits.org/).
The version number and `CHANGELOG.md` are generated from them, so the prefix
determines what happens at release time.

```
<type>(<scope>): <summary>

<body: what changed and, more importantly, why>
```

| Type | Effect | Use for |
|---|---|---|
| `feat` | minor bump | new capability |
| `fix` | patch bump | corrected behaviour |
| `perf` | patch bump | measured speed or memory improvement |
| `docs` | no bump | manuscript, README, comments |
| `test` | no bump | tests and property batteries |
| `ci` | no bump | workflows |
| `build` | no bump | build scripts, flags, dependencies |
| `refactor`, `chore` | no bump | hidden from the changelog |

Append `!` after the type (or add a `BREAKING CHANGE:` footer) for an
incompatible API change.

The body matters more than the summary here. Several of this project's
commits record a finding rather than an edit — a guard that the optimiser was
folding away, a compiler-dependent floating-point mode leak — and the reasoning
is the part worth keeping. Prefer explaining the observation over describing
the diff, which git already shows.

## Before opening a pull request

```bash
./build.sh                              # includes the rounding and MXCSR probes
python3 tests/check_paper_claims.py     # numbers in paper.tex still reproduce
```

CI additionally runs the property batteries, ASan/UBSan, a branch-coverage
report, a portable-versus-native comparison, and a manuscript build across
gcc and clang.

## Two things worth knowing before changing the solver

**The router is untrusted; the checker decides.** The fast path may propose a
status, but nothing it computes constitutes evidence. If a change makes the
router's output feed a certificate more directly, that is a change to the
soundness argument and needs to be argued in the manuscript, not only tested.

**Floating-point flags are part of the contract, not tuning.** `build.sh`
compiles the router with `-ffast-math` and the proof kernels with
`-frounding-math -fno-fast-math`, and keeps `-ffast-math` off the link line.
Each of those is load-bearing and each is checked at build time by a probe.
Changing them requires re-reading the reproducibility section of the
manuscript first.

## Reporting a problem

Useful reports include the compiler and version, the output of `./build.sh`
including both probes, and the failing command with its output. A build that
fails either probe on a toolchain not yet tested is a particularly welcome
report — that is what the probes are for.
