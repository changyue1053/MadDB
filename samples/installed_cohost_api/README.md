# Optional Linux installed API-only cohost

This separate C10/O10 sample exercises the relocated MadDB and MadLink installs
with the existing business sequence and synthetic in-process Link host callbacks.
It opts in to only `MadObs::api` using `COHOST_OBS_API=ON`. Existing OFF and
runtime ON samples, packages and workflows are unchanged. It does not link a
MadObs runtime, initialize a WAL, open a network connection or export anything.

The job stages exact public MadDB `88d78e0`, MadLink `a6d869e` and MadObs
`79fd8ce` commits and verifies their tree IDs. It relocates each install,
deletes producer copies before configuring the app and checks exact imported
targets, API package inventory, link/loader closure and before/after byte hashes.
MadObs is built with the native runtime disabled; only two headers and three
CMake files are expected. A runtime target, archive, header, symbol or zlib link
is not accepted.

The same public DB observation wrapper and Link queued adapter feed one bounded
host-owned collector. It accepts exactly the ordered synthetic event receipt:
connecting, connected, DB put, DB get, closed, DB get. Strict numeric contracts
are pinned; no timestamps/payloads or borrowed event pointers are retained.
One real idempotent remove of an absent key still returns success; its single
valid observation is excluded locally, not recorded. An emitted callback is
not runtime admission or export. The DB still reopens and reads the original
value and Link progresses while DB is closed. These tests do not claim product
integration, persistence under crash, authentication, network or mobile proof.

The branch-only Linux CI reuses existing pinned Rust preparation and stock
tooling. Offline builds and synthetic test execution start after preparation.
No artifacts or release. Portable collector/inventory tests must not be relabeled
as the native installed cohost result.
