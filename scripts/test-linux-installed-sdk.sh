#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
root=$PWD
work=$(mktemp -d "$(realpath "${TMPDIR:-/tmp}")/maddb-linux.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT
exec 3>&1
exec >>"$work/local.log" 2>&1
stage=linux-sdk-install
trap 'printf "FAIL: %s\n" "$stage" >&3' ERR
bash scripts/install-linux-c-sdk.sh "$work/original"
prefix="$work/relocated SDK"
mv -- "$work/original" "$prefix"
test ! -e "$work/original"
export LC_ALL=C
unset LD_LIBRARY_PATH LD_PRELOAD LD_AUDIT CMAKE_PREFIX_PATH MadDB_DIR MadDB_ROOT
cd "$work"
for app in a b; do
    stage=linux-sdk-consumer-$app-build
    consumer="$work/consumer-$app"
    cp -R "$root/linux-consumers/app-$app" "$consumer"
    cmake -S "$consumer" -B "$work/build-$app" \
      -DMadDB_DIR="$prefix/lib/cmake/MadDB" -DMADDB_EXPECTED_PREFIX="$prefix" \
      -DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF -DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF
    cmake --build "$work/build-$app" --parallel 2
    stage=linux-sdk-consumer-$app-link
    binary="$work/build-$app/consumer-$app"
    ldd "$binary" > "$work/ldd-$app"
    python3 - "$work/ldd-$app" "$prefix/lib/libmaddb.so" <<'PY'
from pathlib import Path
import re
import sys
details = Path(sys.argv[1]).read_text()
hits = re.findall(r'^\s*libmaddb\.so\s+=>\s+(.+?)\s+\(0x[0-9a-fA-F]+\)\s*$', details, re.M)
if hits != [sys.argv[2]] or 'not found' in details or 'libsqlite3.so' in details:
    raise SystemExit(1)
PY
    mkdir "$work/store-$app"
done
# Each command is a distinct process. Identical namespace/key, distinct files/data.
for mode in write read; do
    for app in a b; do
        stage=linux-sdk-consumer-$app-$mode
        "$work/build-$app/consumer-$app" "$work/store-$app/store.sqlite" "$mode"
    done
done
# Verify each program rejects the other store's value (a mismatch must
# be explicit, not a launch failure, missing key, bad ABI or generic error).
for app in a b; do
    stage=linux-sdk-consumer-$app-other-value
    other=a
    if [[ $app == a ]]; then other=b; fi
    rc=0
    "$work/build-$app/consumer-$app" "$work/store-$other/store.sqlite" read || rc=$?
    test "$rc" = 2
done
printf 'PASS: two independent installed Linux consumers store and reopen distinct data\n' >&3
