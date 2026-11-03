# gEDA PCB for macOS (experimental fork)

This is a macOS-focused fork of [gEDA PCB](https://github.com/gEDA-pcb-developers/pcb),
a printed circuit board layout editor. It builds the existing GTK2 interface
with the native Quartz backend, without requiring an XQuartz server.
The PCB file format is preserved. GTK3 is outside the current scope.

The fork adds build and packaging scripts, a native application launcher,
targeted editor tests and two source patches for relocatable translations
and a separate macOS configuration profile. The patches are applied to a
build snapshot; the upstream C files in this checkout remain unchanged.

The current target is Apple Silicon with Homebrew in `/opt/homebrew`,
on macOS 26 or newer. Homebrew is needed to build; the standalone `PCB.app`
bundles its runtime dependencies. The application has a local ad hoc signature
and is not notarized. Intel and older macOS versions have not been validated.

- [Dependencies, build instructions and application packaging](contrib/macos/README.md)
- [Validation results and known limitations](contrib/macos/VALIDATION.md)
- [Issues for this fork](https://github.com/tio-checo/pcb-macos/issues)
- [Original upstream README](README) and [license](COPYING)

Build products and application binaries are generated locally, outside the
checkout. No prebuilt release is included in this repository.
