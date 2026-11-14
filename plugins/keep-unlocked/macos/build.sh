#!/bin/sh
# Builds bin/keep-unlocked-keeper (arm64 + x86_64) and signs it with a Developer ID (hardened runtime).
# Usage: macos/build.sh ["Developer ID Application: Name (TEAMID)"]
set -eu
cd "$(dirname "$0")/.."
ID=${1:-$(security find-identity -v -p codesigning | sed -n 's/.*"\(Developer ID Application:[^"]*\)".*/\1/p' | head -1)}
[ -n "$ID" ] || { echo "no Developer ID Application identity" >&2; exit 1; }
T=$(mktemp -d)
for a in arm64 x86_64; do swiftc -O -framework IOKit -target $a-apple-macos12 macos/keeper.swift -o "$T/$a"; done
lipo -create "$T/arm64" "$T/x86_64" -output bin/keep-unlocked-keeper
rm -rf "$T"
codesign -f -s "$ID" -o runtime --timestamp -i dev.claude-utils.keep-unlocked-keeper bin/keep-unlocked-keeper
codesign -dv bin/keep-unlocked-keeper 2>&1 | grep -E 'Identifier|Authority=Developer|Runtime'
