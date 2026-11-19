# MadDB: standalone SQLite SDK prototype

A newly written Rust SDK that each app can embed without MadObs, an account,
a server, or networking. This is an early prototype, not a production release.

```rust
let mut db = maddb::Database::open("app-owned.sqlite", "com.example.app")?;
db.put("key", b"binary value")?;
assert_eq!(db.get("key")?, Some(b"binary value".to_vec()));
# Ok::<(), maddb::Error>(())
```

## Implemented

- Real bundled SQLite, on-disk persistence and explicitly ephemeral SQLite memory mode.
  There is no in-memory mock backend. `open` rejects empty paths, the special
  `:memory:` name, and `file:` SQLite URIs; only `in_memory` opts into ephemeral
  storage. Ordinary filesystem paths use explicit flags without URI support.
- Parameter-bound binary key/value CRUD and ordered atomic batches.
- Logical namespaces, schema identity/version checks, rollback on failure,
  refusal to initialize nonempty foreign SQLite files.
- Optional `madobs` feature exposes in-process counters only. No exporter, logging,
  telemetry upload, observer callbacks, or dependency on the MadObs product.
- Dedicated database files only, 5-second busy timeout, SQLite's default rollback
  journal (not an untested WAL or replication implementation).

## Boundaries

Storage is **plaintext**, including journals; encryption is not implemented. No
SQLCipher, key management, key rotation, secure erase, cloud sync, vector engine,
or encryption compatibility is claimed. A namespace is not an authorization or
security boundary. Prefer one file per app inside the app's OS sandbox; anyone
with file access can read all namespaces. Open trusted, application-owned paths
only; schema checks are not a sandbox for attacker-controlled SQLite files.
Host apps own path choice, directories, permissions, backup and lifecycle.

This is a synchronous Rust library tested on Linux only. Use a background worker
where blocking the UI matters. Rust applications can integrate it directly; there
is no C ABI, Swift/Kotlin binding, WASM bundle, mobile package, async pool, or tested
multi-process workload yet. No schema migration beyond creating version 1 exists.
The `madobs` feature is a narrow future integration seam, not the MadObs SDK.

## Reproduce with an existing Rust toolchain and C compiler

```
cargo test --locked
cargo test --locked --all-features
cargo run --locked --example standalone
cargo build --locked --release
```

See DEPENDENCIES.md and VALIDATION.md for versions, provenance, and verification.
Cargo.lock is intentional even for this library prototype. Registry caches and
build artifacts are ignored and must not be published. Remaining production release gates: security advisory review, platform CI,
binding design, concurrency/crash testing, and any separately designed encryption
support. Crates.io publication remains disabled (`publish = false`).

## License

First-party MadDB code is licensed under MIT; see LICENSE. Third-party dependencies
retain their own licenses. Exact locked dependency notices and provenance are
in THIRD_PARTY_NOTICES.md and third-party/.
