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
for variant in device simulator; do
  if [[ $variant == device ]]; then
    target=aarch64-apple-ios; sdk=iphoneos; swift_target=arm64-apple-ios15.0; module=arm64-apple-ios
  else
    target=aarch64-apple-ios-sim; sdk=iphonesimulator; swift_target=arm64-apple-ios15.0-simulator; module=arm64-apple-ios-simulator
  fi
  export SDKROOT
  SDKROOT=$(xcrun --sdk "$sdk" --show-sdk-path)
  [[ $(xcrun --sdk "$sdk" --show-sdk-version) == 26.2 ]]
  # Only this invocation overrides the manifest crate types; Linux/Android unchanged.
  cargo rustc --lib --crate-type staticlib --locked --offline --release \
    --target "$target" --no-default-features --features c-api
  framework="$out/$variant/MadDB.framework"
  mkdir -p "$framework/Modules/MadDB.swiftmodule" "$framework/Resources/Notices" "$framework/Headers"
  xcrun --sdk "$sdk" swiftc ios/Sources/MadDatabase.swift \
    -target "$swift_target" -sdk "$SDKROOT" -swift-version 5 -O \
    -module-name MadDB -enable-library-evolution -emit-library -emit-module \
    -emit-module-path "$framework/Modules/MadDB.swiftmodule/$module.swiftmodule" \
    -emit-module-interface-path "$framework/Modules/MadDB.swiftmodule/$module.swiftinterface" \
    -I "$out/cmodule" -lresolv -liconv -Xlinker -rpath -Xlinker /usr/lib/swift \
    -Xlinker -load_hidden \
    -Xlinker "$CARGO_TARGET_DIR/$target/release/libmaddb.a" \
    -Xlinker -install_name -Xlinker '@rpath/MadDB.framework/MadDB' \
    -o "$framework/MadDB"
  cp include/maddb.h "$framework/Headers/"
  cp LICENSE THIRD_PARTY_NOTICES.md DEPENDENCIES.md "$framework/Resources/Notices/"
  cp -R third-party "$framework/Resources/Notices/"
  python3 - "$framework" "$sdk" "$(xcrun --sdk "$sdk" --show-sdk-build-version)" <<'PY'
import plistlib, sys
from pathlib import Path
root, sdk, sdk_build = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
assert sdk in ('iphoneos', 'iphonesimulator') and sdk_build
plist = dict(CFBundleIdentifier='io.maddb.sdk', CFBundleName='MadDB',
             CFBundleExecutable='MadDB', CFBundlePackageType='FMWK',
             CFBundleInfoDictionaryVersion='6.0', CFBundleDevelopmentRegion='en',
             DTPlatformName=sdk, DTPlatformVersion='26.2',
             DTSDKName=sdk + '26.2', DTSDKBuild=sdk_build,
             DTXcode='2620', DTXcodeBuild='17C52',
             CFBundleShortVersionString='0.1.0', CFBundleVersion='1',
             MadDBPackageVersion='0.1.0-preview.1', MadDBCABIVersion=1,
             MinimumOSVersion='15.0', CFBundleSupportedPlatforms=[
                 'iPhoneOS' if sdk == 'iphoneos' else 'iPhoneSimulator'])
(root / 'Info.plist').write_bytes(plistlib.dumps(plist))
PY
done
xcodebuild -create-xcframework -framework "$out/device/MadDB.framework" \
  -framework "$out/simulator/MadDB.framework" -output "$out/MadDB.xcframework"
python3 scripts/inspect-ios-package.py "$out/MadDB.xcframework"
