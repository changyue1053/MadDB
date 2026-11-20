#!/usr/bin/env bash
# Local developer installation, not a release or an upload.
set -euo pipefail
[[ $# == 1 && -n $1 ]] || { echo 'Supply one new destination directory' >&2; exit 1; }
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]]
case $1 in
    /*) destination=$1 ;;
    *) destination=$PWD/$1 ;;
esac
[[ ! -e $destination && ! -L $destination ]]
cd "$(dirname "$0")/.."
build=$(mktemp -d)
trap 'rm -rf -- "$build"' EXIT
export RUSTUP_TOOLCHAIN=1.100.0 CARGO_TARGET_DIR="$build"
cargo build --locked --offline -p maddb --release --no-default-features --features c-api
# Create this directory exclusively after a successful offline build.
mkdir -- "$destination"
mkdir -p -- "$destination/include" "$destination/lib/cmake/MadDB" "$destination/share/MadDB"
cp include/maddb.h "$destination/include/"
cp "$build/release/libmaddb.so" "$destination/lib/"
cp packaging/linux/MadDBConfig.cmake "$destination/lib/cmake/MadDB/"
cp LICENSE THIRD_PARTY_NOTICES.md DEPENDENCIES.md "$destination/share/MadDB/"
cp -R third-party "$destination/share/MadDB/"
