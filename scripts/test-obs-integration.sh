#!/usr/bin/env bash
# Real Linux dynamic-link integration, separate from the C ABI-stub contract test.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
exec 3>&1
mkdir -p target/obs-real
exec >>target/obs-real/local.log 2>&1
stage=obs-header-preflight
trap 'printf "FAIL: %s\n" "$stage" >&3' ERR
: "${MADOBS_INCLUDE_DIR:?independently staged exact public header required}"
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]]
[[ $(git hash-object "$MADOBS_INCLUDE_DIR/madobs/observer.h") == 2fd8c8cc81b2e38569c2b2ce3cd5fec03ffcf001 ]]
export RUSTUP_TOOLCHAIN=1.100.0
export CARGO_TARGET_DIR="$PWD/target/obs-real/rust"
stage=obs-real-rust-library
cargo build --locked --offline --features c-api
stage=obs-real-consumer-link
cc -std=c11 -Wall -Wextra -Werror -pedantic -Iinclude -Iadapters/obs \
  -I"$MADOBS_INCLUDE_DIR" adapters/obs/test_real.c \
  -L"$CARGO_TARGET_DIR/debug" -Wl,-rpath,"$CARGO_TARGET_DIR/debug" -lmaddb -o target/obs-real/consumer
stage=obs-real-sqlite-local-sink
./target/obs-real/consumer
printf 'PASS: actual SQLite put/get and local observer dispatch\n' >&3
