#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Explicit serial required: do not select or alter an arbitrary connected device.
: "${ANDROID_SERIAL:?Set the authorized ARM64 test device/emulator serial}"
# A secondary translated ARM ABI on an x86 emulator is not ARM64 proof.
# Require an explicit page-size gate; no implicit 4K/16K success or old flag.
[[ -z ${REQUIRE_16K+x} ]] || { echo 'Use EXPECTED_PAGE_SIZE=4096 or 16384 instead of REQUIRE_16K' >&2; exit 1; }
case ${EXPECTED_PAGE_SIZE:-} in
    4096|16384) ;;
    *) echo 'Set EXPECTED_PAGE_SIZE to exactly 4096 or 16384' >&2; exit 1 ;;
esac
machine=$(adb -s "$ANDROID_SERIAL" shell uname -m | tr -d '\r')
[[ $machine == aarch64 || $machine == arm64 ]] || { echo 'Requires an ARM64 kernel, not translated ARM libraries' >&2; exit 1; }
abi=$(adb -s "$ANDROID_SERIAL" shell getprop ro.product.cpu.abi | tr -d '\r')
[[ $abi == arm64-v8a ]] || { echo 'Requires primary Android ABI arm64-v8a' >&2; exit 1; }
page_size=$(adb -s "$ANDROID_SERIAL" shell getconf PAGE_SIZE | tr -d '\r')
[[ $page_size == "$EXPECTED_PAGE_SIZE" ]] || { echo "Expected page size $EXPECTED_PAGE_SIZE, got $page_size" >&2; exit 1; }
echo "Target runtime kernel: $machine; primary ABI: $abi; page size: $page_size"
adb -s "$ANDROID_SERIAL" install -r android/smoke-app/build/outputs/apk/debug/smoke-app-debug.apk
adb -s "$ANDROID_SERIAL" install -r android/smoke-app/build/outputs/apk/androidTest/debug/smoke-app-debug-androidTest.apk
result=$(adb -s "$ANDROID_SERIAL" shell am instrument -w -r \
    -e maddb_expected_page_size "$EXPECTED_PAGE_SIZE" io.maddb.smoke.test/android.test.InstrumentationTestRunner)
printf '%s\n' "$result"
grep -Fq 'OK (1 test)' <<< "$result"
if grep -Eq 'FAILURES|INSTRUMENTATION_FAILED|Process crashed' <<< "$result"; then
    exit 1
fi
