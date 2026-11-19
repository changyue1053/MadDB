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
