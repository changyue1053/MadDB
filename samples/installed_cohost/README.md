# Installed Linux cohost pilot

One app exercises independent MadDB and MadLink operations with the same behavior
in two physically separate jobs. OFF installs only those two SDKs. ON adds one
installed MadObs private runtime with a bounded synthetic policy and host-owned
local discard callback. It does not use a server, sibling development checkout
paths, a real transport, credentials, or user values.

## Pins and build evidence

| SDK | Public source commit | Source tree |
| --- | --- | --- |
| MadDB | `5395df380c06d86f56e835585f3a2827abd9f397` | `48e5337ad19060fa10ced5bd92896c2f76d1eb5a` |
| MadLink | `a6d869efd8a5b3f2eb1f31e9b5c1a37392251867` | `e6ee8b6ef2c8f8bfd30e5ac90ae05d7811a12350` |
| MadObs, ON only | `79fd8ced44a18bca574598ff683cd706ded16a60` | `fa87aed52ec6d748addacb2f8d57ac30e5976271` |

The producer copies are created from byte-pinned Git trees, use each SDK's own
installer, then are deleted before the app configures. Each package moves to a
spaced prefix. Imported target paths and actual link inputs must match; the
dynamic loader must resolve MadDB by name to that exact staged shared library.
The core MadLink and optional null-provider MadObs archives are linked by
absolute relocated paths, not library-search fallbacks. Core input package
bytes are checked before and after. Both app modes use the exact same test source.
The ON lane stages the existing two public optional adapter headers separately;
neither default SDK package is changed. OFF never fetches, stages or links MadObs.

`verify.py` takes pre-existing local pinned Git objects and an already available
locked Cargo cache plus Rust 1.100.0, CMake, compiler, and host zlib for ON. It
does not fetch. The exact hosted branch uses the prior reviewed Rust/registry
preparation, then reads the named public Git pins into job-private scratch
without credentials or redirects. No package, dependency, log or executable
is attached, uploaded or published by this workflow.

## Functional contract

- DB opens app-local SQLite, writes and reads fixed binary data. Link accepts a
  different fixed byte using an injected in-process callback; the public
  tracked completion is local acceptance, not peer delivery.
- Link continues after DB closes. DB reopens the same synthetic store and
  continues after Link closes and is destroyed.
- In ON, the existing public MadDB adapter reports the completed operation
  separately from the DB result. The existing Link queue reports only finite
  state values after poll. Both feed one host-owned policy/runtime. There are
  exactly three accepted reports from each source, six drains and no queue
  or WAL drops. The policy rejects a real DB REMOVE observation while the
  DB operation still succeeds. The local sink validates every offered batch
  against the combined policy; neither raw bytes nor user fields are retained.
  Both producer paths stop before the observer; ordinary DB calls still work
  after it is destroyed. These proofs are admission, drain and local privacy
  validation, not per-event exporter acknowledgments.

No cross-SDK calls, shared product state, production adapter changes, transfer,
physical/mobile execution, replay/durability/remote-delivery claim, full ABI
compatibility matrix, security audit or release. Local compile/synthetic guard
success does not imply the installed runtime gate passed.
