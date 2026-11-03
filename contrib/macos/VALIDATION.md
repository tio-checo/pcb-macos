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
integration with Lepton EDA have not been fully validated. The complete
upstream image regression suite was not run; the selected text cases were.
Finder document association is not configured. The old `~/.pcb` settings
are not imported automatically.

Two macOS-only patches are applied to the archived build snapshot: a runtime
locale directory and a separate PCB settings profile. Bundle helper scripts
are also adjusted for spaces in paths and bundled GNU m4. The original
upstream C files remain unchanged in the checkout.
