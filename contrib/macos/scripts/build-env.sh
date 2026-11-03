#!/bin/sh
set -eu
macos_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
src=$(CDPATH= cd -- "$macos_dir/../.." && pwd)
root=$(CDPATH= cd -- "$src/.." && pwd)
macos_major=$(/usr/bin/sw_vers -productVersion | /usr/bin/cut -d. -f1)
exec /usr/bin/env -i HOME="$HOME" TMPDIR="${TMPDIR:-/tmp}" \
  PATH="$root/build/tools/bin:/opt/homebrew/opt/bison/bin:/opt/homebrew/opt/texinfo/bin:/opt/homebrew/opt/flex/bin:/opt/homebrew/opt/gettext/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
  ACLOCAL_PATH="$root/build/tools/share/aclocal" \
  LC_ALL=C CC=/usr/bin/clang CXX=/usr/bin/clang++ CFLAGS="-g -O2 -std=gnu99" \
  PKG_CONFIG=/opt/homebrew/bin/pkg-config \
  PKG_CONFIG_LIBDIR="/opt/homebrew/lib/pkgconfig:/opt/homebrew/share/pkgconfig:/opt/homebrew/opt/libffi/lib/pkgconfig:/opt/homebrew/Library/Homebrew/os/mac/pkgconfig/$macos_major" \
  "$@"
