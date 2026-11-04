# Native PCB build for macOS

These scripts build gEDA PCB using GTK2/Quartz and package a relocatable
`PCB.app`. The supported build environment is Apple Silicon, macOS 26 or
newer, Apple's Command Line Tools and Homebrew in `/opt/homebrew`.
Python 3.9 or newer is required; `/usr/bin/python3` was used for validation.

## Workspace layout

Keep the source clone in a dedicated parent directory. Run the commands below
from the source checkout; its name does not matter:

```sh
mkdir -p ~/projects/pcb-macos
cd ~/projects/pcb-macos
git clone https://github.com/tio-checo/pcb-macos.git pcb
cd pcb
```

The scripts derive all paths from their own location. The parent directory
contains `build/`, `install/`, `dist/` and `docs/logs/`; source files and macOS
support remain in `pcb/`. Use one checkout per workspace. The source checkout
must be clean. The build uses `git archive HEAD` and refuses to reuse a source
snapshot from a different commit. Use a path without spaces for compiling the
legacy Autotools project; the finished application supports paths with spaces.

## Dependencies

Install Apple's Command Line Tools (`xcode-select --install`) and Homebrew.
The Homebrew dependencies used by this build are:

```sh
brew install autoconf automake libtool pkgconf gettext texinfo flex bison m4 \
  gtk+ gd librsvg adwaita-icon-theme hicolor-icon-theme shared-mime-info
```

GTK2 must expose the `quartz` backend. The preflight check rejects X11 GTK2.
Bison 3 is required; the old system Bison cannot parse this source tree.
The clean build environment explicitly selects GNU99 for the bundled GTS code
and includes the Homebrew metadata for macOS SDK libraries.

Also provide intltool >= 0.35 with its Perl dependencies and `intltool.m4`.
The validated installation used MacPorts intltool 0.51.0 in `/opt/local`
(`sudo port install intltool` on a configured MacPorts installation).
If intltool is installed in Homebrew it is preferred. For another location,
set `INTLTOOL_PREFIX=/absolute/prefix` when running preflight and the build.
Only these build tools are linked into `build/tools/`; MacPorts library paths
are never added to the build or runtime environment.

```sh
sh contrib/macos/scripts/preflight.sh
sh contrib/macos/scripts/build-gtk2.sh
sh contrib/macos/scripts/test-gtk2.sh
```

Build logs are in the parent workspace's `docs/logs/`. `BUILD_JOBS=4` changes
the default parallel build limit of 6. The build disables OpenGL, D-Bus,
document generation, desktop database updates and the Tcl/Tk QFP generator.

## Standalone application

After the build and checks:

```sh
/usr/bin/python3 contrib/macos/scripts/build-app.py
/usr/bin/python3 contrib/macos/scripts/audit-app.py ../dist/PCB.app
open ../dist/PCB.app
```

The packager refuses to overwrite an existing `../dist/PCB.app`; move a
previous result aside first. It copies dependency libraries and GTK modules,
rewrites their load commands, includes data and licenses, and signs all native
images and the application locally. It also embeds the exact source archive,
patches, packaging scripts and a provenance manifest. The packager does not
change installed Homebrew libraries.

Copy the whole `PCB.app` to `/Applications` if desired. It runs independently
of Homebrew, MacPorts and the source workspace. It uses Quartz; some indirect
Cairo dependencies still include bundled X11 libraries. An X11 server is not
needed. The current application is about 113 MB and contains 75 native arm64
images; this can vary with installed dependency versions.

Open board files using File → Open. Open the footprint library using
Window → Library or `i`. Finder document association is not configured.
Check opening Preferences with fresh and configured library settings using:

```sh
/usr/bin/python3 contrib/macos/scripts/test-preferences.py --app ../dist/PCB.app
```

The test uses disposable profiles and leaves user preferences unchanged.
Command line examples:

```sh
../dist/PCB.app/Contents/MacOS/PCB -V
../dist/PCB.app/Contents/MacOS/PCB /absolute/path/board.pcb
../dist/PCB.app/Contents/MacOS/PCB -x png --outfile /tmp/board.png /absolute/path/board.pcb
```

## User profile

The standalone application's profile is
`~/Library/Application Support/PCB-Quartz/`. PCB settings live below `.pcb/`
inside this profile, including `settings`, `preferences` and `pcbrc` as needed.
XDG data, configuration, module caches and temporary files also stay in the
profile. The application does not import the old `~/.pcb` settings.
The actual HOME remains available to file dialogs and `~` paths.
A launch without arguments writes diagnostic output to `editor.log` in the
profile. `PCB_BUNDLE_PROFILE=/absolute/path` selects a test profile.

Window dimensions are saved on normal exit, including File → Quit and the
window's close button, and restored on the next launch. They are stored as
`top-window-width` and `top-window-height` in `.pcb/preferences` under the
profile. Forced termination does not save settings.

## Import schematics from Lepton EDA

The standalone PCB application includes a `gnetlist` compatibility entry point
and a `pcbfwd` backend for Lepton. File → Import Schematics → gschem now uses
Lepton's netlister, passing footprints, values, connections, pin labels and
selected component attributes to PCB. LeptonEDA.app must be installed to use
this optional import feature; it is not bundled into PCB.

The bridge looks for LeptonEDA.app beside PCB.app, then in `/Applications`,
then in `~/Applications`. To select a different installation, put its absolute
application path on a single line in
`~/Library/Application Support/PCB-Quartz/lepton-app`. This is a data file,
not a shell script. An explicitly configured invalid path reports an error
instead of selecting a different installation.

The backend is loaded from PCB's own resources; Lepton's installed files are
not changed. Lepton uses its own normal profile for symbol libraries.
An explicit `LEPTON_BUNDLE_PROFILE` is preserved for isolated integration tests.
PCB footprint libraries still need their own configuration; locating schematic
symbols in Lepton does not configure PCB's footprint search path.

To add a local footprint directory, create or edit
`~/Library/Application Support/PCB-Quartz/.pcb/preferences` and add a line such as:

```text
library-newlib = ~/PCB-footprints
```

Use your actual footprint directory. This setting adds it to the bundled
footprint libraries. Restart PCB after changing preferences. Imported footprint
names must match files in an available library. A deleted component restored
by import needs manual placement and clearance checks.

The import checks the netlister's exit status before applying any commands.
Missing Lepton, a netlister error or an unsupported oversized action record
leaves the board unchanged. Normal Finder launches record stderr diagnostics
in the PCB profile's `editor.log`. This PCB version accepts action lines up to
254 UTF-8 bytes; the backend rejects longer records and literal newlines in
arguments with a diagnostic rather than sending truncated commands.

After packaging, test the complete integration with public fixtures:

```sh
/usr/bin/python3 contrib/macos/scripts/test-import.py --app ../dist/PCB.app
```

This test uses separate PCB and Lepton profiles, imports a two-component
schematic, deletes and restores D3, verifies exact connectivity and checks
failed and partially written netlist output. It does not use personal designs
or modify existing application settings.

## Development and editor tests

The development bundle depends on this checkout and Homebrew:

```sh
sh contrib/macos/scripts/build-dev-app.sh
sh contrib/macos/scripts/run-gtk2.sh
/usr/bin/python3 contrib/macos/scripts/test-editor.py
```

It uses the workspace's `build/runtime-home/` instead of the normal user profile
and opens a working copy of the public LED example by default. Pass absolute
paths for other boards. This bundle is not for installation or distribution.

Test the standalone bundle through its public `--listen` command interface:

```sh
/usr/bin/python3 contrib/macos/scripts/test-editor.py --app ../dist/PCB.app
```

The test edits a copy of the public LED board, uses a disposable profile,
closes its own editor and saves results in a `session-*` directory.
It leaves unrelated editor sessions alone. It checks 25 conditions including
library indexing, edit/undo/redo, rotated pin coordinates, save/reopen,
legacy m4 footprint generation, PNG export and isolated settings.

Check saving and restoring window size through the same `Quit()` action used
by File → Quit:

```sh
/usr/bin/python3 contrib/macos/scripts/test-window-size.py --app ../dist/PCB.app
```

This test uses a disposable profile and a public example copy. It forces an
initial geometry change through GTK's minimum-size constraint, checks saved
preferences after normal exit, and compares actual Quartz window dimensions
after restart. It needs the macOS graphical session and Command Line Tools;
it does not use accessibility or modify the normal user profile.

The File → Open Recent submenu matches Lepton EDA: ten numbered boards,
most recently used first, with full paths in tooltips. Successful opens
(including the command line) and Save As update the list. Choosing an entry
uses the same unsaved-layout confirmation as File → Open. The GTK history is
stored in `~/Library/Application Support/PCB-Quartz/data/recently-used.xbel`
and survives restarts. It is separate from Lepton's history and does not
migrate an existing `~/.recently-used.xbel`. Paste-buffer loads and failed
opens are excluded.

Check the actual GTK recent-file menu in disposable profiles:

```sh
/usr/bin/python3 contrib/macos/scripts/test-recent-files.py --app ../dist/PCB.app
```

The test-only GTK module inspects and activates real menu entries, including
paths with spaces, Unicode, quotes and commas. It checks confirmation/cancel,
MRU ordering, limits, filtering, Save As, restart persistence, deleted files,
profile isolation and an immediate Save As followed by Quit. It needs the
GTK2 development headers and Command Line Tools; it does not use accessibility
or change the normal profile. The test module is never a runtime dependency.

Check Thin Draw Poly and Thin Draw using actual GTK/GDK renderer pixels:

```sh
/usr/bin/python3 contrib/macos/scripts/test-thin-draw.py --app ../dist/PCB.app
```

This test requires the GTK2 development headers and Command Line Tools used
for building. It loads a test-only GTK module, captures offscreen pixmaps of
a generated polygon and trace, and checks normal fill, outlines, trace width,
restoration after toggling and filled Gerber export. It uses a disposable
profile; screen recording and accessibility permissions are not needed. The
fix is confined to GDK; the OpenGL renderer retains its translucent polygon
fill, and exporters retain filled copper.

For an independent relocation check, copy the app outside the workspace.
Both the app and test directory must be outside the blocked workspace:

```sh
check_dir=$(mktemp -d /private/tmp/pcb-relocation.XXXXXX)
mkdir "$check_dir/Moved PCB"
ditto ../dist/PCB.app "$check_dir/Moved PCB/PCB.app"
/usr/bin/python3 contrib/macos/scripts/audit-app.py "$check_dir/Moved PCB/PCB.app"
/usr/bin/python3 contrib/macos/scripts/test-editor.py \
  --app "$check_dir/Moved PCB/PCB.app" --run-parent "$check_dir/runs" --sandbox
```

The sandbox denies reads of `/opt/homebrew`, `/opt/local` and the parent
workspace. A small test helper enables a real dyld trace inside that sandbox,
so an empty trace cannot pass the library check. Review the results, then
remove only the temporary directory created for this test.
See [VALIDATION.md](VALIDATION.md) for the scope and remaining limitations.
