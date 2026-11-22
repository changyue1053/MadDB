# Optional MadDB-to-MadObs observer adapter

This opt-in header-only adapter is not a Cargo dependency and is not included
in the default Linux SDK install. The Cargo feature `madobs` remains independent
local Rust counters. The adapter does not expose those counters, change the C
ABI, start a runtime, or alter database operation results.

`maddb_obs_get` and `maddb_obs_put` call MadDB and report only the operation and
its returned status. `maddb_obs_report_result` can report an independently
managed operation; it cannot verify that an operation happened. Only fixed
enum fields are reported: no timestamps, identifiers, file paths, or payloads
are passed to the observer. Callback invocation is not runtime admission,
durable storage, or export. Hosts own callback lifetime and serialization and
must avoid recursion. A size probe and copy are two C calls.

Use an independently supplied MadObs `include/madobs/observer.h` from public
commit `4af77ffa464a48307e5ff2d95f10b835919d205b`, Git blob
`2fd8c8cc81b2e38569c2b2ce3cd5fec03ffcf001`. No MadObs header, source, archive,
license grant, or runtime policy is included in this repository. The MadDB
adapter is under the existing MadDB MIT license. The host is responsible for
its authorization and use of the separately obtained observer API.

```sh
export MADOBS_INCLUDE_DIR=/absolute/public/MadObs/include
make -C adapters/obs test
bash scripts/test-obs-integration.sh
```

The first command compiles and runs C11/C++17 contract fixtures with explicitly
synthetic C ABI stubs and a local callback; it is not SQLite execution. The
second independently checks the header pin, then uses the existing locked
offline Linux Rust build to test a real in-memory SQLite database and local
observer callback. The test covers binary data, probe/short-buffer, missing
versus empty, unchanged DB results when observation fails, removal, and closed
handle status. Neither command needs a MadObs runtime or service.
