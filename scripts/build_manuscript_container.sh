#!/usr/bin/env bash
# Run the persistent toolchain image against host files. Only the temporary
# container is removed: the downloaded image and workspace artifacts remain.
set -euo pipefail

if [[ ${1:-} == --help ]]; then
    printf 'Usage: bash scripts/build_manuscript_container.sh [workspace-directory]\n'
    printf 'The workspace must contain paper.tex, references.bib and build_paper.sh.\n'
    printf 'The pinned image is downloaded only if absent; paper.pdf stays on the host.\n'
    exit 0
fi
if (( $# > 1 )); then
    echo 'expected at most one workspace directory' >&2
    exit 2
fi
tool_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
texlive_image=$(< "$tool_root/ci/texlive/image.txt")
if [[ ! $texlive_image =~ ^ghcr\.io/metronforge/affine-bundle-solver-texlive@sha256:[0-9a-f]{64}$ ]]; then
    echo 'invalid immutable TeX image reference' >&2
    exit 2
fi
manuscript_workspace=$(cd "${1:-$tool_root}" && pwd)
if [[ $manuscript_workspace == *,* ]]; then
    echo 'workspace path must not contain a comma (Docker mount syntax)' >&2
    exit 2
fi
exec docker run --rm --pull=missing --network=none --read-only \
    --tmpfs /tmp:rw,nosuid,size=128m --cap-drop=ALL \
    --security-opt=no-new-privileges --user "$(id -u):$(id -g)" \
    --env HOME=/tmp --mount "type=bind,source=$manuscript_workspace,target=/work" \
    --workdir /work "$texlive_image" abs-build-manuscript
