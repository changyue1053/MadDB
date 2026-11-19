#!/usr/bin/env bash
# Separate Linux-only real runtime gate. No installs, SDK publication or networking sink.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
[[ ${MADDB_WITH_MADOBS_RUNTIME:-OFF} == ON ]] || { echo 'FAIL: runtime requires explicit ON'; exit 1; }
root=$PWD
mkdir -p target/obs-runtime
exec 3>&1
exec >>target/obs-runtime/local.log 2>&1
stage=runtime-prerequisites
trap 'printf "FAIL: %s\n" "$stage" >&3' ERR
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]]
for tool in cmake make git pkg-config c++ cargo ldd; do command -v "$tool" >/dev/null; done
pkg-config --exists zlib
python3 scripts/test-obs-runtime-dependencies.py
out="$root/target/obs-runtime"
[[ ! -e "$out/prefix" && ! -e "$out/consumer-build" ]]
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
mkdir "$scratch/home" "$scratch/source"
public_git() {
  env -i PATH="$PATH" HOME="$scratch/home" LC_ALL=C \
    GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0 \
    git -C "$scratch/source" -c credential.helper= -c http.extraHeader= "$@"
}
pin=4af77ffa464a48307e5ff2d95f10b835919d205b
stage=runtime-anonymous-source
public_git init -q
public_git fetch --depth=1 --no-tags https://github.com/changyue1053/MadObs.git "$pin"
[[ $(public_git rev-parse FETCH_HEAD) == "$pin" ]]
public_git checkout --detach FETCH_HEAD
[[ $(public_git hash-object include/madobs/observer.h) == 2fd8c8cc81b2e38569c2b2ce3cd5fec03ffcf001 ]]
stage=runtime-static-null-provider
# Same public null-provider installation recipe; no inherited provider discovery.
env -i PATH="$PATH" HOME="$scratch/home" LC_ALL=C cmake -S "$scratch/source" -B "$scratch/build" \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF -DMADOBS_BUILD_RUNTIME=ON \
  -DMADOBS_BUILD_SHARED=OFF -DMADOBS_BUILD_JNI=OFF -DMADOBS_PACKAGE_BORINGSSL=OFF \
  -DIMOBS_BORINGSSL_ROOT= -DIMOBS_BORINGSSL_INCLUDE= -DIMOBS_BORINGSSL_CRYPTO_LIB=
cmake --build "$scratch/build" --parallel 2
cmake --install "$scratch/build" --prefix "$out/prefix"
stage=runtime-maddb-library
export RUSTUP_TOOLCHAIN=1.100.0
export CARGO_TARGET_DIR="$out/rust"
cargo build --locked --offline --features c-api
mkdir -p "$out/maddb/include" "$out/maddb/lib"
cp include/maddb.h adapters/obs/maddb_obs.h "$out/maddb/include/"
cp "$CARGO_TARGET_DIR/debug/libmaddb.so" "$out/maddb/lib/"
# Remove only the MadObs producer trees; MadDB checkout/build remain present.
# Consumer link configuration uses the installed MadObs and staged MadDB artifacts.
rm -rf "$scratch/source" "$scratch/build"
stage=runtime-installed-consumer
cmake -S adapters/obs/runtime -B "$out/consumer-build" -DMADDB_WITH_MADOBS_RUNTIME=ON \
  -DMADOBS_PREFIX="$out/prefix" -DMADDB_PREFIX="$out/maddb" \
  -DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF -DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF
cmake --build "$out/consumer-build" --parallel 2
stage=runtime-no-network-provider-dependencies
# Explicit checker fails on forbidden/missing dependencies; negated grep alone
# is exempt from shell errexit and must not be used as a gate.
python3 scripts/check-obs-runtime-dependencies.py "$out/consumer-build/consumer" "$out/maddb/lib/libmaddb.so" >&3 2>&3
stage=runtime-local-admission-drain
mkdir -m 700 "$scratch/wal"
env -u LD_LIBRARY_PATH -u LD_PRELOAD -u LD_AUDIT timeout 30 "$out/consumer-build/consumer" "$scratch/wal"
printf 'PASS: real SQLite to installed static MadObs admission/drain and bounded local batch check\n' >&3
