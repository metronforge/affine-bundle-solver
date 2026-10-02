#!/usr/bin/env bash
# Run the persistent toolchain image against host files. Only the temporary
# container is removed: the downloaded image and workspace artifacts remain.
set -euo pipefail

if [[ ${1:-} == --help ]]; then
    printf 'Usage: bash scripts/build_manuscript_container.sh [workspace-directory] [-- command [args...]]\n'
    printf 'Without a command, runs the compatibility abs-build-manuscript command.\n'
    printf 'With --, runs your repository script or TeX command in /work.\n'
    exit 0
fi
tool_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
texlive_image=$(< "$tool_root/ci/texlive/image.txt")
if [[ ! $texlive_image =~ ^ghcr\.io/metronforge/texlive-custom@sha256:[0-9a-f]{64}$ ]]; then
    echo 'invalid immutable TeX image reference' >&2
    exit 2
fi

workspace=${1:-$tool_root}
if [[ ${1:-} == -- ]]; then
    workspace=$tool_root
fi
if (( $# > 0 )) && [[ $1 != -- ]]; then
    shift
fi
if (( $# > 0 )); then
    if [[ $1 != -- ]]; then
        echo 'custom command must follow --' >&2
        exit 2
    fi
    shift
    if (( $# == 0 )); then
        echo 'expected a command after --' >&2
        exit 2
    fi
    container_command=("$@")
else
    container_command=(abs-build-manuscript)
fi

manuscript_workspace=$(cd "$workspace" && pwd)
if [[ $manuscript_workspace == *,* ]]; then
    echo 'workspace path must not contain a comma (Docker mount syntax)' >&2
    exit 2
fi
exec docker run --rm --pull=missing --network=none --read-only \
    --tmpfs /tmp:rw,nosuid,size=128m --cap-drop=ALL \
    --security-opt=no-new-privileges --user "$(id -u):$(id -g)" \
    --env HOME=/tmp --mount "type=bind,source=$manuscript_workspace,target=/work" \
    --workdir /work "$texlive_image" "${container_command[@]}"
