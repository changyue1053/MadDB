# MadDB: standalone SQLite SDK preview

MadDB is an embeddable, synchronous Rust key/value library. It uses bundled
SQLite and needs no account, server, network connection, or sibling SDK at
runtime. This is source for a developer preview, not a production release.

```rust
let mut db = maddb::Database::open("app-owned.sqlite", "com.example.app")?;
db.put("key", b"binary value")?;
assert_eq!(db.get("key")?, Some(b"binary value".to_vec()));
# Ok::<(), maddb::Error>(())
```

The library has binary values, parameter-bound CRUD, ordered atomic batches,
logical namespaces, and schema identity checks. It refuses to initialize a
nonempty foreign SQLite file. `Database::open` rejects empty paths, SQLite URI
paths, and the special `:memory:` name; use `Database::in_memory` explicitly for
an ephemeral database. The optional `madobs` feature is limited to in-process
counters and does not depend on the MadObs product.

## Linux C ABI and local installation

Enable `c-api` to expose the version 1 ABI declared in [maddb.h](include/maddb.h).
Handles are process-local opaque tokens, with operation locking per handle.
The caller owns input and output buffers. Reads distinguish missing from empty,
never return a Rust pointer, and never partially copy. The header documents
pointer, buffer, and close-race requirements.

The [Linux installed SDK guide](linux-consumers/README.md) shows how to install
and relocate the shared library and consume it with independent C11 and C++17
projects. The acceptance fixture covers separate stores and one cross-process
SQLite write-lock rejection and recovery; it does not claim general concurrency
or crash durability.

With a suitable Rust toolchain, compilers, and already cached locked dependencies:

```sh
cargo test --locked --offline
cargo test --locked --offline --all-features
cargo run --locked --offline --example standalone
bash scripts/test-c-api.sh
bash scripts/test-linux-installed-sdk.sh --lock-recovery
```

The installed SDK scripts target Linux x86_64 and use Rust 1.100.0. See
[validation](VALIDATION.md) for the evidence and remaining checks, and
[dependency provenance](DEPENDENCIES.md) for exact versions and checksums.

## Boundaries

Storage and journals are plaintext. A namespace is not an authorization
boundary. Use trusted application-owned files inside the application's OS
sandbox; callers own permissions, backup and lifecycle. Calls can block,
including SQLite's bounded busy wait, so avoid blocking a UI thread.
The source does not implement encryption, migration beyond schema 1, WAL,
replication, or a network exporter. Mobile bindings and optional cohost
experiments are outside this integration. Cargo publication and binary release
are not enabled by this source snapshot.

First-party MadDB code is [MIT](LICENSE). Third-party components retain their
own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md).
