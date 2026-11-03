#!/bin/sh
set -eu
macos_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
src=$(CDPATH= cd -- "$macos_dir/../.." && pwd)
root=$(CDPATH= cd -- "$src/.." && pwd)
envscript="$macos_dir/scripts/build-env.sh"
sh "$macos_dir/scripts/preflight.sh"
mkdir -p "$root/build/source" "$root/build/gtk2" "$root/docs/logs" \
  "$root/build/tools/bin" "$root/build/tools/share/aclocal"
# intltool is a build-time tool only; never add MacPorts to the library paths.
if [ -n "${INTLTOOL_PREFIX:-}" ]; then
  intltool_prefix=$INTLTOOL_PREFIX
elif [ -x /opt/homebrew/bin/intltoolize ]; then
  intltool_prefix=/opt/homebrew
else
  intltool_prefix=/opt/local
fi
for tool in intltoolize intltool-extract intltool-merge intltool-update; do
  test -x "$intltool_prefix/bin/$tool"
  ln -sf "$intltool_prefix/bin/$tool" "$root/build/tools/bin/$tool"
done
test -f "$intltool_prefix/share/aclocal/intltool.m4"
ln -sf "$intltool_prefix/share/aclocal/intltool.m4" "$root/build/tools/share/aclocal/intltool.m4"
test -x /opt/homebrew/opt/bison/bin/bison
test "$(sh "$envscript" pkg-config --variable=target gdk-2.0)" = quartz
test -z "$(git -C "$src" status --porcelain)"
if [ ! -f "$root/build/source/.source-commit" ]; then
  git -C "$src" archive HEAD | tar -x -C "$root/build/source"
  git -C "$src" rev-parse HEAD > "$root/build/source/.source-commit"
fi
if [ "$(cat "$root/build/source/.source-commit")" != "$(git -C "$src" rev-parse HEAD)" ]; then
  echo "Source snapshot differs from checkout HEAD; use a fresh build/source directory." >&2
  exit 1
fi
sh "$macos_dir/scripts/apply-source-patches.sh"
cd "$root/build/source"
sh "$envscript" env GIT_DIR="$(git -C "$src" rev-parse --absolute-git-dir)" ./autogen.sh > "$root/docs/logs/bootstrap.log" 2>&1
cd "$root/build/gtk2"
sh "$envscript" env WISH=/usr/bin/true ../source/configure \
  --with-libintl-prefix=/opt/homebrew/opt/gettext --prefix="$root/install/gtk2" --with-gui=gtk --disable-gl --disable-dbus \
  --disable-doc --disable-update-desktop-database --disable-update-mime-database \
  --disable-xrender --disable-xinerama \
  > "$root/docs/logs/configure.log" 2>&1
sh "$envscript" make -j"${BUILD_JOBS:-6}" > "$root/docs/logs/build.log" 2>&1
sh "$envscript" make install > "$root/docs/logs/install.log" 2>&1
echo "Installed in $root/install/gtk2"
