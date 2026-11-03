#!/bin/sh
set -eu
macos_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
src=$(CDPATH= cd -- "$macos_dir/../.." && pwd)
root=$(CDPATH= cd -- "$src/.." && pwd)
mkdir -p "$root/docs/logs" "$root/build/smoke" "$root/build/regression"
sh "$macos_dir/scripts/build-env.sh" make -C "$root/build/gtk2/src" check \
  > "$root/docs/logs/unit-tests.log" 2>&1
cd "$root/build/smoke"
sh "$macos_dir/scripts/pcb-gtk2.sh" -x png --outfile LED.png "$src/example/LED.pcb" \
  > "$root/docs/logs/export-png.log" 2>&1
sh "$macos_dir/scripts/pcb-gtk2.sh" -x gerber --gerberfile LED "$src/example/LED.pcb" \
  > "$root/docs/logs/export-gerber.log" 2>&1
cd "$root/build/regression"
sh "$macos_dir/scripts/build-env.sh" env srcdir="$src/tests" top_srcdir="$src" \
  PCB="$macos_dir/scripts/pcb-gtk2.sh" sh "$src/tests/run_tests.sh" \
  hid_bom1 hid_bom2 hid_bom3 hid_bom4 hid_bom5 hid_bom6 hid_bom7 hid_bom8 hid_bom9 hid_bom10 \
  hid_bom_md1 hid_ipcd3561 hid_ipcd3562 hid_ipcd3563 hid_ipcd3564 hid_ipcd3565 \
  hid_ipcd3566 hid_ipcd3567 hid_ipcd3568 hid_ipcd3569 hid_ipcd35610 hid_ipcd35611 \
  hid_ipcd35612 hid_ipcd35613 hid_ipcd35614 hid_ipcd35615 hid_ipcd35616 \
  > "$root/docs/logs/regression-text.log" 2>&1
cat "$root/build/gtk2/src/unittest.log"
tail -1 "$root/docs/logs/regression-text.log"
