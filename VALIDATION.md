# Validation summary

## Previously verified implementation (2026-11-18)

The unchanged Rust source, schema, tests and example were tested on Linux with
rustc/cargo 1.100.0. Bundled SQLite runtime reported version 3.54.1.

- `cargo test --locked`: 13 integration tests passed.
- `cargo test --locked --all-features`: 14 integration tests passed.
- `cargo run --locked --example standalone`: passed.
- `cargo build --locked --release`: passed.
- `RUSTDOCFLAGS='-D warnings' cargo doc --locked --no-deps --all-features`: passed.

Coverage includes binary/empty values, bound SQL parameters, CRUD, persistence,
logical namespaces, atomic batch rollback, schema identity/version validation,
foreign file rejection, explicit ephemeral paths, and optional local counters.
Regression cases include rejecting `sqliteX_customer` foreign tables without file
changes, refusing empty / `:memory:` / `file:` URI paths in `open`, and allowing a
literal `:memory:` filename within an ordinary directory to persist.

## Publication packaging (2026-11-19)

Only licensing, Cargo package metadata, third-party notices, and documentation
changed for this snapshot. Implementation, test, example and Cargo.lock bytes
match the previously tested source. All 11 dependency archives were fetched from
the public crates.io distribution service and verified against Cargo.lock SHA-256
checksums before their original notices were collected. No dependency code is
vendored here, and no raw build or execution logs are included.

No Rust toolchain is available in the packaging environment, so the final package
was not rebuilt. The declared Rust 1.89 minimum follows the upstream rusqlite
requirement but has not been tested as a minimum supported compiler here.

## Not verified

Formatting/lint checks could not run because rustfmt and clippy were unavailable
in the original toolchain. No current advisory audit, cross-platform build,
crash/power-loss exercise, hostile database test, cross-process concurrency stress,
or performance benchmark has been completed. There is no encryption implementation
or encryption validation claim. Passing local tests is not a production-readiness
claim.

## Linux CI definition

The source-check workflow targets GitHub-hosted Ubuntu 24.04 and exactly Rust
1.100.0, not a floating stable toolchain. It fetches dependencies with Cargo.lock
locked, then runs default-feature tests, all-feature tests, and the standalone
example offline. Checkout is pinned to the public actions/checkout v7.0.1 commit.
Permissions are read-only; checkout credentials are not persisted. There are no
secret inputs, cache/artifact uploads, deployment steps, releases, or package
publishing. Only normal push and pull_request events are used.

This workflow definition has been statically checked but has not yet run. Its
addition is not evidence that CI passed. It does not test the declared minimum
Rust version or platforms other than Linux. GitHub's hosted runner image can change
within the Ubuntu 24.04 label; the Rust compiler and package lock are pinned.


## Native ABI candidate (not yet executed)

The optional `c-api` slice adds versioned symbols, non-reused opaque handles,
per-handle serialization, stable statuses, and caller-owned binary copy buffers.
New tests cover empty versus missing, exact/short buffer behavior, stale handles,
invalid arguments/UTF-8, concurrent close, lock independence and panic containment.
A C11 consumer exercises on-disk reopen and binary CRUD through the shared library;
a C++17 consumer checks header linkage. Both are connected to the pinned Linux CI.

Local checks passed: C11/C++17 syntax under warning-as-error flags, shell syntax,
workflow YAML parse, unchanged dependency lock, and whitespace checks. No local
Rust toolchain is available: new Rust tests, shared-library build, linkage and
host execution have NOT run. Earlier green CI covers only the prior source, not
this ABI candidate. The declared minimum Rust/compiler/platform claims are unchanged.

## Android-native candidate

The Android slice preserves Rust source, C ABI/header, Cargo manifest and lock.
Local checks: shell/YAML/XML parsing; JNI C warning-as-error syntax check using the
public Android JNI header; pure-Java wrapper/smoke classes compiled with the existing
JDK compiler module using source/target 17. This host compiler uses JDK 21 APIs:
`--release 17` was unavailable in the local stripped runtime, so Android/Java API
compatibility remains a real Gradle/SDK build gate. Generated JNI descriptors match
the C registration signatures. No fake native library or Android runtime was used.

No Rust Android compiler, NDK, Gradle, SDK, adb or device was installed locally.
Android compilation/linking, AAR/APK inspection, instrumentation execution and 16 KiB
runtime tests have not run. Hosted build-only workflow is prepared but not published
or executed as part of this source change. See android/README.md for exact gates.
