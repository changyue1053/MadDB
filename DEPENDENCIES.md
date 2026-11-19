# Dependency policy and provenance

The direct dependency is exactly pinned to rusqlite 0.43.0, with default features
disabled and only bundled SQLite enabled. Cargo.lock pins all 11 registry packages
and their checksums. Previously tested bundled SQLite runtime: 3.54.1.

On 2026-11-19, each package was fetched from static.crates.io and its complete
archive SHA-256 verified against Cargo.lock before copying license files.
See THIRD_PARTY_NOTICES.md for the complete inventory and third-party/provenance.json
for machine-readable provenance. All collected license files are verbatim upstream
texts; no dependency implementation is vendored.

First-party SDK code is MIT. Third-party packages retain their licenses. Crates.io
publication remains disabled while this prototype matures. A current advisory
audit and platform validation remain outstanding; locked versions do not imply
security review or production readiness.

Public primary references:
- https://docs.rs/crate/rusqlite/0.43.0
- https://docs.rs/crate/libsqlite3-sys/0.40.0
- https://www.sqlite.org/copyright.html
