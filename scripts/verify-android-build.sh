#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${ANDROID_HOME:?Set ANDROID_HOME}"
gradle_bin="${GRADLE_BIN:-gradle}"
"$gradle_bin" --version | grep -Fx 'Gradle 8.9'
# No wrapper download, license acceptance, tool install, or device connection here.
"$gradle_bin" -p android --no-daemon :maddb:versionedAar
"$gradle_bin" -p android --no-daemon :smoke-app:assembleDebug :smoke-app:assembleDebugAndroidTest
base=android/maddb/build/versioned
apk=android/smoke-app/build/outputs/apk/debug/smoke-app-debug.apk
python3 scripts/inspect-android-package.py "$base/maddb-android-0.1.0-preview.1-arm64-v8a.aar" "$apk"
"$ANDROID_HOME/build-tools/35.0.0/zipalign" -c -P 16 -v 4 "$apk"
git diff --exit-code -- Cargo.lock
