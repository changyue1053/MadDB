# Validation summary

This source integration selects the reviewed standalone Rust library,
experimental C ABI, installed Linux acceptance fixtures, optional observer
adapter, and standalone iOS Swift packaging and consumer sources. It adds no
workflow, cross-repository cohost, Android/HarmonyOS binding, binary, or release.

## Historical exact-source evidence

| Scope | Earlier public checkpoint | Result |
| --- | --- | --- |
| Linux Rust default/all features and standalone example | [e512bbf](https://github.com/changyue1053/MadDB/commit/e512bbfd8a26f72fd2f3f5543c92eaea36071490) | [Source checks passed](https://github.com/changyue1053/MadDB/actions/runs/44443466795) |
| Linux Rust and C ABI, including linked C/C++ consumers | [5c7e7c3](https://github.com/changyue1053/MadDB/commit/5c7e7c3f380649df80ca5c43a3deaeeff9344c99) | [Source and ABI checks passed](https://github.com/changyue1053/MadDB/actions/runs/44449683497) |
| Linux x86_64 relocated installed SDK, independent C/C++ stores | [5395df3](https://github.com/changyue1053/MadDB/commit/5395df380c06d86f56e835585f3a2827abd9f397) | [Installed SDK gate passed](https://github.com/changyue1053/MadDB/actions/runs/44733515180) |
| Linux x86_64 installed SDK, uncommitted write-lock witness and recovery | [cd2f42c](https://github.com/changyue1053/MadDB/commit/cd2f42ccede1872dd7b831cb02fb066e2a1fa5de) | [Lock recovery gate passed](https://github.com/changyue1053/MadDB/actions/runs/44824043824) |

The selected core, C ABI, manifest, lockfile, ordinary tests and examples are
byte-identical to the C ABI checkpoint. Linux packaging, consumers and lock
fixture are byte-identical to the lock recovery checkpoint, apart from this
integration's documentation. Those runs are evidence for the identified
checkpoint files, not a fresh run on this combined commit.

The lock fixture verifies that an independently held, uncommitted transaction
causes `MADDB_STORAGE_ERROR` without changing the visible value; a second store
still writes and reopens while the first is locked. The first live handle
recovers after rollback, and fresh processes confirm exact distinct values.

## Fresh Linux integration checks

The exact candidate source was tested on Linux x86_64 with Rust/Cargo 1.100.0
and CMake 3.25.1. All 11 crate archives were independently verified against
their Cargo.lock SHA-256 checksums after locked fetch. Every build and test
then ran offline.

- `cargo test --locked --offline`: 13 passed.
- `cargo test --locked --offline --all-features`: 19 passed (2 unit,
  14 storage-contract, and 3 C ABI contract tests).
- `cargo run --locked --offline --example standalone`: passed.
- `bash scripts/test-c-api.sh`: linked C11 and C++17 consumers passed.
- `bash scripts/test-linux-installed-sdk.sh --lock-recovery`: both independent
  relocated consumers, exact lock-rejection/recovery, and store isolation passed.

Portable checks also passed for the lock orchestrator with real SQLite and a
non-SDK synthetic peer, strict C11/C++17 syntax, shell syntax, and lock-to-notice
consistency. Recording these results changed only this validation document.

No minimum Rust version qualification, current security advisory audit,
physical-device runtime, crash/power-loss test, long-running contention test, or
production readiness is claimed. The package is unencrypted.


## Optional observer adapter

The opt-in C11/C++17 contract fixtures and the separate real in-memory
SQLite-to-local-observer test passed on the current Linux x86_64 source with
Rust/Cargo 1.100.0 and the exact independently staged public observer header.
The actual Rust library was built locked and offline. This adds no fresh
cross-repository cohost, mobile, runtime/WAL, or export claim; the standalone
library, C ABI and Linux install paths are unchanged.


## Standalone iOS source provenance

The producer, Swift API, independent binary consumer and verifier scripts match
[public checkpoint 4274af59](https://github.com/changyue1053/MadDB/commit/4274af59b0f577ddd14de0cb710f73e7f10baa65).
Its [hosted run](https://github.com/changyue1053/MadDB/actions/runs/44638052469)
built and inspected both slices, compiled the unsigned device consumer, and
passed all 10 named tests on an ARM64 iOS 26.2 Simulator. The Rust core, C ABI,
Cargo files, and notices are unchanged from that checkpoint. This integration
passed 7 portable package-inspector tests, 5 result-parser tests, shell syntax,
and scheme XML checks; no Apple build or run was performed on this integration
commit. There is no claimed physical-device, minimum-iOS runtime, or release
validation. The independent store fixture runs two stores inside one hosted
app process; it is not a two-app or concurrent-process claim.
