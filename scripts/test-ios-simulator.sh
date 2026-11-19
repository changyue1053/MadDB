#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export DEVELOPER_DIR=/Applications/Xcode_26.2.app/Contents/Developer
[[ $(uname -m) == arm64 ]]
[[ $(xcodebuild -version) == $'Xcode 26.2\nBuild version 17C52' ]]
# No runtime downloads, license acceptance, discovery or connection of physical devices.
runtime=com.apple.CoreSimulator.SimRuntime.iOS-26-2
type=com.apple.CoreSimulator.SimDeviceType.iPhone-16
xcrun simctl list runtimes available -j | python3 -c '
import json,sys
assert any(r["identifier"] == "com.apple.CoreSimulator.SimRuntime.iOS-26-2" and r["isAvailable"] for r in json.load(sys.stdin)["runtimes"]), "Required preinstalled iOS 26.2 runtime missing"
'
uuid=$(xcrun simctl create "MadDB-${GITHUB_RUN_ID:-local}-$$" "$type" "$runtime")
cleanup() {
  xcrun simctl shutdown "$uuid" >/dev/null 2>&1 || true
  xcrun simctl delete "$uuid" >/dev/null 2>&1 || true
}
trap cleanup EXIT
xcrun simctl boot "$uuid"
xcrun simctl bootstatus "$uuid" -b
[[ $(xcrun simctl spawn "$uuid" uname -m) == arm64 ]]
xcodebuild -project ios/Smoke/MadDBSmoke.xcodeproj -scheme MadDBSmoke \
  -destination "platform=iOS Simulator,id=$uuid" -destination-timeout 120 \
  -derivedDataPath build/ios/simulator-consumer \
  -resultBundlePath build/ios/simulator-tests.xcresult \
  -parallel-testing-enabled NO ARCHS=arm64 ONLY_ACTIVE_ARCH=YES \
  CODE_SIGNING_ALLOWED=YES CODE_SIGN_IDENTITY=- CODE_SIGNING_REQUIRED=NO test
