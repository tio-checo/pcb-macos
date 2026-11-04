# Validation and limitations

Validated on 3 November 2026 using Apple Silicon, macOS 26.7.1 and Apple Clang
21.0.0. The upstream base is commit
`a38ac3e999f388219adadecee0add6b56eb36c6e`.

## Toolchain

The tested Homebrew environment used GTK2 2.24.33 (Quartz), GLib 2.90.1,
Cairo 1.18.6, Pango 1.58.2, GD 2.3.3, Autoconf 2.73, Automake 1.19,
Bison 3.8.2 and Flex 2.6.4. Intltool 0.51.0 was supplied by MacPorts as a
build-time tool only. These versions describe the tested environment;
Homebrew dependencies are not pinned by this repository.

## Automated checks

- Three upstream unit tests passed (`pcb-printf` and `object-list`).
- Twenty-seven text regression cases passed: `hid_bom1`–`hid_bom10`,
  `hid_bom_md1`, and `hid_ipcd3561`–`hid_ipcd35616`, without changing references.
- The public LED example exported to PNG and to seven Gerber plus two drill
  files. Manufacturing correctness was not independently verified.
- The standalone editor passed 25 checks through the official `--listen`
  interface, including undo/redo, placement, rotation with pin coordinate
  validation, via creation, save/reopen, all 53 library groups, legacy m4
  generation, PNG export and profile isolation.
- The app passed the same checks after moving to a path with spaces, while
  a runtime sandbox blocked Homebrew, MacPorts and the whole workspace.
  The actual dyld trace included the bundled GTK Quartz libraries/modules
  and no Homebrew or MacPorts runtime paths.
- Audits of the original and relocated apps passed for 75 arm64 native files,
  contained symlinks, library closure, absence of external rpaths and valid
  local ad hoc signatures.

The build and test scripts write raw logs, JSON summaries and generated files
to the parent workspace, outside Git. No private design files, personal
configuration, host-specific loader traces or application binaries are
included in this repository. The test uses the upstream public LED example.

## Lepton import checks

The new `test-import.py` suite passed 23 checks using separate PCB and Lepton
profiles and a public two-component schematic. It verifies automatic discovery
and configured application paths with spaces, multiple source files, quoted
values, exact nets and pin labels, component attributes, and restoration of D3
after deletion while preserving R1 placement. Missing Lepton, failed netlisters
with partial output and oversized records leave the board unchanged.

All 23 checks also passed with the app moved to a path with spaces, while a
sandbox denied reads of Homebrew, MacPorts and both source/build workspaces.
The changed app passed the 25 existing editor checks, library/signature audit,
3 upstream unit tests and 27 selected text regression cases. The final packaged
app passed these checks again, including import after relocation with reads
of Homebrew, MacPorts and both source/build workspaces denied.

A separate test on a disposable copy of a private project passed 27 checks.
The board and schematic contain 61 components and 48 nets. Deleting a component
and running Import() restored its footprint from a configured local library,
value and pin labels. All imported connections matched an independent Lepton
tEDAx netlist. The other 60 components kept their positions and footprint
geometry; all ten layer records and four vias remained unchanged. Import also
updated nine previously unknown values from the schematic.

The resulting board saved, reopened and exported to PNG. Coordinate comparisons
allowed for the precision of PCB's printed mm/mil units. The original project,
local footprint and user configuration files were unchanged. Private project
files and personal library paths are excluded from this repository; the public
fixture uses bundled footprints only.

A restored component is inserted as a new component and needs manual placement
and clearance checks. Its default position can overlap existing copper and
produce temporary connectivity warnings. The previous position of a deleted
component is not recovered by schematic import.

## Window size on normal Quit

Validated on 4 November 2026. The new `test-window-size.py` reproduced the
missing preferences write in the previous app. After the GTK cleanup callback
was added, all ten checks passed: normal Quit writes the changed geometry
and complete preferences, and a second launch restores the same actual Quartz
window size. Both sessions exit normally without GTK critical errors.
A startup `Quit()` before the GTK main loop also exits cleanly without critical
errors. The test uses the same `Quit()` action as File → Quit, a disposable
profile and the public LED example; it does not require accessibility automation.

The rebuilt standalone app also passed the 25 editor checks, all three upstream
unit checks and the audit of 75 arm64 native images, bundled dependencies and
local ad hoc signatures. The user's existing profile was not changed.

## Manual checks

The development editor was checked for window display and resize, zoom,
panning, the footprint library, Export menu, Save As and reopening that copy.
The user also confirmed correct display of the LED board and a working
footprint library in the standalone PCB application.

Automated macOS accessibility inspection of the legacy GTK2 window timed out.
The command-interface checks are not a full test of dialog usability. Zoom
and pan remain manual checks because the corresponding PCB actions can wait
for a pointer coordinate when the pointer is outside the canvas.

## Limits

The app is a development build with an ad hoc signature, without Apple
notarization or Developer ID signing. It targets arm64 and macOS 26 or newer;
Intel and older systems have not been validated. No prebuilt release or CI
build is provided yet.

GTK3 is not implemented. OpenGL, D-Bus and the Tcl/Tk QFP footprint generator
are disabled. Printing, all advanced exporters, clipboard behavior and
the complete workflow on personal projects have not been fully validated.
Lepton integration now has a dedicated public-fixture test (`test-import.py`),
including restore-after-delete, exact nets and failed-netlister isolation.
The complete upstream image regression suite was not run; the selected text cases were.
Finder document association is not configured. The old `~/.pcb` settings
are not imported automatically.

Six macOS-only patches are applied to the archived build snapshot: a runtime
locale directory, a separate PCB settings profile, import child-process
status checking, GTK final cleanup so File → Quit saves preferences, and safe
handling of an unset custom library preference, and polygon fill suppression
in GUI thin draw modes. Bundle helper scripts are also
adjusted for spaces in paths and bundled GNU m4. The original upstream C files
remain unchanged in the checkout.

## Preferences crash fix (4 November 2026)

Opening File → Preferences with an unset `library-newlib` passed NULL to
`gtk_entry_set_text`, causing a segmentation fault in the bundled GTK2 build.
Patch 0005 displays an empty string when no custom library is configured.

The rebuilt app passed repeated Preferences actions with fresh, unset, empty
and configured library settings through `test-preferences.py`. The test uses
disposable profiles and the same `DoWindows(Preferences)` action as the menu;
it does not validate all dialog interactions. The public LED board also
loaded and exported to PNG successfully.

## Thin polygon drawing

The final polygon-fill pass in DrawLayer() ignored GUI thin draw flags and
filled polygons again after their outlines had been drawn. Patch 0006 skips
this final fill in GUI Thin Draw Poly and Thin Draw modes. Exporters continue
to fill polygons independently of the saved display flags.

`test-thin-draw.py` uses a generated public fixture and the GTK renderer's
offscreen pixmap to compare actual pixels. It checks polygon interiors and
outlines, trace width, restoration after toggling, unchanged board data and
filled Gerber regions. The capture module is test-only and is never included
as a runtime dependency of the application.

Validated on 4 November 2026: the old app reproduced the filled polygon with
the thin flag enabled. The updated standalone app passed all 16 GTK pixel,
board-preservation and Gerber checks, plus 25 editor checks, three upstream
unit checks and the audit of 75 native arm64 images. The installed app passed
the 16 rendering checks and bundle audit again. User designs and settings were
not used by these tests.
