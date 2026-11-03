#!/bin/sh
set -eu
macos_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
src=$(CDPATH= cd -- "$macos_dir/../.." && pwd)
root=$(CDPATH= cd -- "$src/.." && pwd)
exec sh "$macos_dir/scripts/runtime-env.sh" "$root/install/gtk2/bin/pcb" "$@"
