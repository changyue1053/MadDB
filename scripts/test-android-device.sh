#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Explicit serial required: do not select or alter an arbitrary connected device.
: "${ANDROID_SERIAL:?Set the authorized ARM64 test device/emulator serial}"
abi=$(adb -s "$ANDROID_SERIAL" shell getprop ro.product.cpu.abilist | tr -d '\r')
[[ ",$abi," == *,arm64-v8a,* ]] || { echo 'Requires real ARM64 Android runtime' >&2; exit 1; }
page_size=$(adb -s "$ANDROID_SERIAL" shell getconf PAGE_SIZE | tr -d '\r')
echo "Target runtime ABI: $abi; page size: $page_size"
if [[ ${REQUIRE_16K:-0} == 1 ]]; then
    [[ $page_size == 16384 ]] || { echo '16 KiB runtime required, not available' >&2; exit 1; }
fi
adb -s "$ANDROID_SERIAL" install -r android/smoke-app/build/outputs/apk/debug/smoke-app-debug.apk
adb -s "$ANDROID_SERIAL" install -r android/smoke-app/build/outputs/apk/androidTest/debug/smoke-app-debug-androidTest.apk
result=$(adb -s "$ANDROID_SERIAL" shell am instrument -w -r io.maddb.smoke.test/android.test.InstrumentationTestRunner)
printf '%s\n' "$result"
grep -Fq 'OK (1 test)' <<< "$result"
! grep -Eq 'FAILURES|INSTRUMENTATION_FAILED|Process crashed' <<< "$result"
