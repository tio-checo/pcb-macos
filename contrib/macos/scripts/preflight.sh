#!/bin/sh
set -eu
fail() { echo "PCB macOS: $*" >&2; exit 1; }
[ "$(/usr/bin/uname -m)" = arm64 ] || fail "This build targets Apple Silicon (arm64)."
major=$(/usr/bin/sw_vers -productVersion | /usr/bin/cut -d. -f1)
[ "$major" -ge 26 ] || fail "This build currently requires macOS 26 or newer."
/usr/bin/xcrun --find clang >/dev/null || fail "Install Apple's Command Line Tools."
for tool in autoconf automake aclocal glibtoolize pkg-config rsvg-convert; do
  [ -x "/opt/homebrew/bin/$tool" ] || fail "Missing Homebrew tool: $tool"
done
for tool in bison/bin/bison flex/bin/flex gettext/bin/autopoint gettext/bin/msgfmt texinfo/bin/makeinfo m4/bin/m4; do
  [ -x "/opt/homebrew/opt/$tool" ] || fail "Missing Homebrew tool: $tool"
done
prefix=${INTLTOOL_PREFIX:-}
if [ -z "$prefix" ]; then
  if [ -x /opt/homebrew/bin/intltoolize ]; then prefix=/opt/homebrew; else prefix=/opt/local; fi
fi
for tool in intltoolize intltool-extract intltool-merge intltool-update; do
  [ -x "$prefix/bin/$tool" ] || fail "Missing $tool; provide intltool and set INTLTOOL_PREFIX."
done
[ -f "$prefix/share/aclocal/intltool.m4" ] || fail "Missing intltool.m4 in $prefix."
macos_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
envscript="$macos_dir/scripts/build-env.sh"
[ "$(sh "$envscript" pkg-config --variable=target gdk-2.0)" = quartz ] || fail "GTK2 must use the Quartz backend."
sh "$envscript" pkg-config --exists gtk+-2.0 cairo pangocairo || fail "Missing GTK2/Cairo/Pango development metadata."
[ -f /opt/homebrew/include/gd.h ] || fail "Missing Homebrew gd (PNG export)."
for dir in share/themes/Default share/themes/Raleigh share/themes/Mac share/icons/Adwaita share/icons/hicolor share/mime etc/fonts/conf.d; do
  [ -d "/opt/homebrew/$dir" ] || fail "Missing runtime data: $dir"
done
/usr/bin/python3 -c 'import sys; assert sys.version_info >= (3, 9), "Python 3.9 or newer required"'
echo "Apple Silicon / macOS $(/usr/bin/sw_vers -productVersion); GTK $(sh "$envscript" pkg-config --modversion gtk+-2.0) / Quartz"
echo "intltool prefix: $prefix (build-time only)"
