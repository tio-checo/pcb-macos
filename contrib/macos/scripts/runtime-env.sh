#!/bin/sh
set -eu
macos_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
src=$(CDPATH= cd -- "$macos_dir/../.." && pwd)
root=$(CDPATH= cd -- "$src/.." && pwd)
profile="$root/build/runtime-home"
mkdir -p "$profile" "$profile/config" "$profile/cache" "$profile/data" "$profile/tmp"
exec /usr/bin/env -i HOME="$profile" TMPDIR="$profile/tmp/" \
  XDG_CONFIG_HOME="$profile/config" XDG_CACHE_HOME="$profile/cache" \
  XDG_DATA_HOME="$profile/data" LC_ALL=C \
  PATH="$root/install/gtk2/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
  "$@"
