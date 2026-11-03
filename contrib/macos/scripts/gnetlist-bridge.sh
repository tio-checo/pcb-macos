#!/bin/sh
# Compatibility entry point for PCB's Import() action; no external interpreter.
# SPDX-License-Identifier: GPL-2.0-or-later
set -eu
resources=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
profile=${PCB_BUNDLE_PROFILE:?PCB_BUNDLE_PROFILE is not set}
config="$profile/lepton-app"
lepton_app=
if [ -f "$config" ]; then
  IFS= read -r lepton_app < "$config" || :
  case "$lepton_app" in
    /*) ;;
    *) echo "PCB import: put an absolute LeptonEDA.app path in $config" >&2; exit 127 ;;
  esac
else
  applications=$(CDPATH= cd -- "$resources/../../.." && pwd)
  for candidate in "$applications/LeptonEDA.app" /Applications/LeptonEDA.app "$HOME/Applications/LeptonEDA.app"; do
    if [ -x "$candidate/Contents/Resources/bin/lepton-netlist" ]; then
      lepton_app=$candidate
      break
    fi
  done
fi
netlister="$lepton_app/Contents/Resources/bin/lepton-netlist"
if [ -z "$lepton_app" ] || [ ! -x "$netlister" ]; then
  echo "PCB import: LeptonEDA.app was not found. Install it in /Applications, or put its absolute path in $config" >&2
  exit 127
fi
exec "$netlister" -L "$resources/share/pcb/netlist" "$@"
