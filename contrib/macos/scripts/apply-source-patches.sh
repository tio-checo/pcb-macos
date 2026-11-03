#!/bin/sh
set -eu
macos_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
src=$(CDPATH= cd -- "$macos_dir/../.." && pwd)
root=$(CDPATH= cd -- "$src/.." && pwd)
cd "$root/build/source"
for file in "$macos_dir"/patches/*.patch; do
  if /usr/bin/patch -f -R -p1 --dry-run < "$file" >/dev/null 2>&1; then
    continue
  fi
  /usr/bin/patch -f -p1 --dry-run < "$file" >/dev/null
  /usr/bin/patch -f -p1 < "$file"
done
