#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${ANDROID_HOME:?Set ANDROID_HOME to an existing licensed Android SDK}"
ndk="$ANDROID_HOME/ndk/28.2.13676358"
tools="$ndk/toolchains/llvm/prebuilt/linux-x86_64/bin"
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || { echo 'Only Linux x86_64 build host supported' >&2; exit 1; }
grep -Eq '^Pkg.Revision *= *28\.2\.13676358' "$ndk/source.properties"
export RUSTUP_TOOLCHAIN=1.100.0
[[ $(rustc --version) == 'rustc 1.100.0 '* ]]
command -v cargo >/dev/null
test -x "$tools/aarch64-linux-android26-clang"
export CARGO_TARGET_DIR="$PWD/target/android"
export CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER="$tools/aarch64-linux-android26-clang"
export CC_aarch64_linux_android="$CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER"
export AR_aarch64_linux_android="$tools/llvm-ar"
# Explicit for Rust cdylib as well as the JNI shim, not just NDK default behavior.
export CARGO_TARGET_AARCH64_LINUX_ANDROID_RUSTFLAGS='-C link-arg=-Wl,-z,max-page-size=16384 -C link-arg=-Wl,-soname,libmaddb.so'
cargo build --locked --offline --release --target aarch64-linux-android --no-default-features --features c-api
out="$PWD/android/maddb/build/generated/jniLibs/arm64-v8a"
mkdir -p "$out"
cp "$CARGO_TARGET_DIR/aarch64-linux-android/release/libmaddb.so" "$out/libmaddb.so"
"$tools/aarch64-linux-android26-clang" -std=c11 -Wall -Wextra -Werror -fPIC -shared \
  -Iinclude android/maddb/src/main/c/maddb_jni.c -L"$out" -lmaddb \
  -Wl,-z,defs -Wl,-z,max-page-size=16384 -Wl,-soname,libmaddb_jni.so -o "$out/libmaddb_jni.so"
notices="$PWD/android/maddb/build/generated/assets/maddb-notices"
mkdir -p "$notices"
cp LICENSE THIRD_PARTY_NOTICES.md DEPENDENCIES.md "$notices/"
cp -R third-party "$notices/"
printf 'version=0.1.0-preview.1\nabi=arm64-v8a\nminSdk=26\ncAbi=1\nencryption=none\nobs=disabled\n' > "$notices/package.properties"
