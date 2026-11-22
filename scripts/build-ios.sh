#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $(uname -s) == Darwin && $(uname -m) == arm64 ]] || { echo 'Requires Apple silicon macOS' >&2; exit 1; }
export DEVELOPER_DIR=/Applications/Xcode_26.2.app/Contents/Developer
[[ $(xcodebuild -version) == $'Xcode 26.2\nBuild version 17C52' ]]
export RUSTUP_TOOLCHAIN=1.100.0
[[ $(rustc --version) == 'rustc 1.100.0 '* ]]
export IPHONEOS_DEPLOYMENT_TARGET=15.0
export CARGO_TARGET_DIR="$PWD/target/ios"
out="$PWD/build/ios"
# Deliberately fail on an existing package rather than merging stale slices.
[[ ! -e "$out/MadDB.xcframework" ]]
mkdir -p "$out/cmodule"
cp include/maddb.h "$out/cmodule/"
printf 'module CMadDB { header "maddb.h" export * }\n' > "$out/cmodule/module.modulemap"
# Resources are inputs to Xcode's Copy Bundle Resources phase, not post-archive edits.
mkdir -p "$out/Notices"
cp LICENSE THIRD_PARTY_NOTICES.md DEPENDENCIES.md "$out/Notices/"
cp -R third-party "$out/Notices/"
for variant in device simulator; do
  if [[ $variant == device ]]; then
    target=aarch64-apple-ios; sdk=iphoneos; destination='generic/platform=iOS'
  else
    target=aarch64-apple-ios-sim; sdk=iphonesimulator; destination='generic/platform=iOS Simulator'
  fi
  export SDKROOT
  SDKROOT=$(xcrun --sdk "$sdk" --show-sdk-path)
  [[ $(xcrun --sdk "$sdk" --show-sdk-version) == 26.2 ]]
  # Only this invocation overrides the manifest crate types; Linux/Android unchanged.
  cargo rustc --lib --crate-type staticlib --locked --offline --release \
    --target "$target" --no-default-features --features c-api
  archive="$out/$variant.xcarchive"
  [[ ! -e "$archive" ]] || { echo 'Use a fresh archive output directory' >&2; exit 1; }
  # Xcode owns framework linking, generated/processed Info.plist, module interfaces,
  # standard iOS bundle layout and resource copying. Never rewrite its archive.
  env -u SDKROOT xcodebuild archive -project ios/Framework/MadDB.xcodeproj \
    -scheme MadDB -configuration Release -destination "$destination" \
    -archivePath "$archive" -derivedDataPath "$out/derived-$variant" \
    MADDB_RUST_STATIC_LIBRARY="$CARGO_TARGET_DIR/$target/release/libmaddb.a" \
    ARCHS=arm64 ONLY_ACTIVE_ARCH=NO CODE_SIGNING_ALLOWED=NO
done
xcodebuild -create-xcframework \
  -archive "$out/device.xcarchive" -framework MadDB.framework \
  -archive "$out/simulator.xcarchive" -framework MadDB.framework \
  -output "$out/MadDB.xcframework"
python3 scripts/inspect-ios-package.py "$out/MadDB.xcframework"
