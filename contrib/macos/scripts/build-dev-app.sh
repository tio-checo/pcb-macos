#!/bin/sh
set -eu
macos_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
src=$(CDPATH= cd -- "$macos_dir/../.." && pwd)
root=$(CDPATH= cd -- "$src/.." && pwd)
app="$root/build/PCBDev.app"
mkdir -p "$app/Contents/MacOS" "$root/build/gui" "$root/docs/logs"
sh "$macos_dir/scripts/runtime-env.sh" /usr/bin/true
if [ ! -f "$root/build/gui/LED.pcb" ]; then
  cp "$src/example/LED.pcb" "$root/build/gui/LED.pcb"
fi
ln -sfn "$root/install/gtk2/share" "$app/Contents/share"
cp "$root/install/gtk2/bin/pcb" "$app/Contents/MacOS/PCBEngine"
/usr/bin/clang -std=c99 -Wall -Wextra "$macos_dir/scripts/dev-launcher.c" \
  "-DPROJECT_ROOT=\"$root\"" -o "$app/Contents/MacOS/PCBDev"
/usr/bin/python3 - "$app" <<'PLIST'
import plistlib, sys
from pathlib import Path
app = Path(sys.argv[1])
info = dict(CFBundleExecutable='PCBDev', CFBundleIdentifier='local.geda-pcb.PCBDev',
            CFBundleName='PCBDev', CFBundlePackageType='APPL', CFBundleVersion='1',
            NSHighResolutionCapable=True)
with (app/'Contents/Info.plist').open('wb') as f:
    plistlib.dump(info, f)
PLIST
/usr/bin/plutil -lint "$app/Contents/Info.plist"
