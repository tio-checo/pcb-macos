#!/bin/sh
set -eu
macos_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
src=$(CDPATH= cd -- "$macos_dir/../.." && pwd)
root=$(CDPATH= cd -- "$src/.." && pwd)
# Pass absolute document paths; the launcher works in build/gui.
exec "$root/build/PCBDev.app/Contents/MacOS/PCBDev" "$@"
