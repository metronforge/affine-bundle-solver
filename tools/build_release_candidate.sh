#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "usage: $0 VERSION COMMIT OUTPUT_DIR" >&2
  exit 2
fi

version=$1
commit=$2
output_dir=$3
repo_root=$(cd "$(dirname "$0")/.." && pwd)

if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-.][0-9A-Za-z.-]+)?$ ]]; then
  echo "invalid release version: $version" >&2
  exit 2
fi
if ! git -C "$repo_root" rev-parse --verify "$commit^{commit}" >/dev/null 2>&1; then
  echo "not a commit: $commit" >&2
  exit 2
fi

for required in paper.pdf libaffine_bundle_solver.so \
                libcertified_solver.so libstatus_verifier.so; do
  if [ ! -f "$repo_root/$required" ]; then
    echo "missing generated release input: $required" >&2
    exit 1
  fi
done

mkdir -p "$output_dir"
output_dir=$(cd "$output_dir" && pwd)
work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

tag="v$version"
source_name="affine-bundle-solver-$tag"
research_name="affine-bundle-solver-$tag-research"
source_dir="$work_dir/$source_name"
research_dir="$work_dir/$research_name"
source_epoch=$(git -C "$repo_root" show -s --format=%ct "$commit")

mkdir -p "$source_dir"
git -C "$repo_root" archive "$commit" | tar -x -C "$source_dir"

# SHA256SUMS.txt in old snapshots described a hand-built review directory and
# is not a manifest of the release tree.  Never carry it into a new archive.
rm -f "$source_dir/SHA256SUMS.txt"

make_manifest() {
  local directory=$1
  (
    cd "$directory"
    find . -type f ! -name MANIFEST.sha256 -print0 \
      | LC_ALL=C sort -z \
      | xargs -0 sha256sum > MANIFEST.sha256
  )
}

make_archive() {
  local parent=$1
  local basename=$2
  local destination=$3
  tar --sort=name --mtime="@$source_epoch" --owner=0 --group=0 \
      --numeric-owner --format=posix \
      --pax-option=delete=atime,delete=ctime \
      -C "$parent" -cf - "$basename" | gzip -n > "$destination"
}

make_manifest "$source_dir"
make_archive "$work_dir" "$source_name" \
  "$output_dir/$source_name.tar.gz"

cp -a "$source_dir" "$research_dir"
mkdir -p "$research_dir/prebuilt/linux-x86_64" \
         "$research_dir/reproduction"
cp "$repo_root/paper.pdf" "$research_dir/paper.pdf"
cp "$repo_root/libaffine_bundle_solver.so" \
   "$repo_root/libcertified_solver.so" \
   "$repo_root/libstatus_verifier.so" \
   "$research_dir/prebuilt/linux-x86_64/"
if [ -d "$repo_root/vectorization-report" ]; then
  cp -a "$repo_root/vectorization-report" \
    "$research_dir/reproduction/vectorization-report"
fi
{
  echo "release_version=$version"
  echo "source_commit=$commit"
  echo "source_date_epoch=$source_epoch"
  echo "platform=linux-x86_64"
  echo "compiler=$(${CC:-gcc} --version | head -1)"
  echo "python=$(${PYTHON:-python3} --version 2>&1)"
  echo "python_packages=$(${PYTHON:-python3} -c 'import mpmath,numpy,scipy,threadpoolctl; print("numpy="+numpy.__version__+" scipy="+scipy.__version__+" mpmath="+mpmath.__version__+" threadpoolctl="+threadpoolctl.__version__)')"
} > "$research_dir/reproduction/PROVENANCE.txt"

# The copy inherited the source manifest; replace it after adding generated
# material so every file in the research bundle is covered by one manifest.
rm -f "$research_dir/MANIFEST.sha256"
make_manifest "$research_dir"
make_archive "$work_dir" "$research_name" \
  "$output_dir/$research_name.tar.gz"

(
  cd "$output_dir"
  sha256sum "$source_name.tar.gz" "$research_name.tar.gz" > SHA256SUMS.txt
)

echo "release candidate written to $output_dir"
