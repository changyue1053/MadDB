#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Linux dynamic-link smoke test; no downloads or package installation here.
export CARGO_TARGET_DIR="$PWD/target/c-api"
cargo build --locked --offline --features c-api
build=$(mktemp -d)
trap 'rm -rf "$build"' EXIT
cc -std=c11 -Wall -Wextra -Werror -pedantic -Iinclude examples/c_host.c \
  -L"$CARGO_TARGET_DIR/debug" -Wl,-rpath,"$CARGO_TARGET_DIR/debug" -lmaddb -o "$build/c-host"
printf '#include "maddb.h"\nint main() { return maddb_abi_version() == 1 ? 0 : 1; }\n' > "$build/header.cpp"
c++ -std=c++17 -Wall -Wextra -Werror -pedantic -Iinclude "$build/header.cpp" \
  -L"$CARGO_TARGET_DIR/debug" -Wl,-rpath,"$CARGO_TARGET_DIR/debug" -lmaddb -o "$build/cpp-host"
"$build/c-host" "$build/app.sqlite"
"$build/cpp-host"
