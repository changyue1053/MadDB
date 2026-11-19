# Optional MadDB → MadObs result adapter

This independent header-only integration target is not a Cargo dependency or a
default build. The `madobs` Cargo feature remains Rust-only local counters;
this adapter does not expose those counters or change that feature's semantics.
The stable C ABI currently has no observation/counter accessor. Rather than
change the kernel, the host explicitly opts into `maddb_obs_get` / `maddb_obs_put`.
These forward all arguments to the real C ABI, report only after it returns and
return its unchanged status. The lower-level `maddb_obs_report_result` accepts
only operation/status for separately managed reporting; it cannot verify a call.

Use the independently supplied public MadObs observer header pinned to commit
`4af77ffa464a48307e5ff2d95f10b835919d205b`, blob
`2fd8c8cc81b2e38569c2b2ce3cd5fec03ffcf001`. No MadObs source/header is copied or
redistributed here. Its license and host consent/runtime configuration remain
separate. MadDB's new adapter retains this repository's MIT license.

```
make -C adapters/obs test MADOBS_INCLUDE_DIR=/absolute/public/MadObs/include
```

The test links the actual header adapter and pinned observer implementation to
a local recording callback in C11 and C++17. Supplied statuses are synthetic;
there is no mocked SQLite backend masquerading as database execution. It checks
all nine status mappings, operation validation, no-op/invalid observers, finite
attributes and zero timing/unused fields. No network, runtime library or storage
sink is linked. `EMITTED` means callback invocation only, not admission/export.

Schema: fixed preview SDK ID `0x4D444201`, version 1, events get=1/put=2/remove=3,
one attribute key 1 with values 0..8 in the header's status mapping order. Severity
is informational (1) or error (3). Unknown status/operation fails closed. It
accepts no caller string, handle, path, payload, length or timestamp. Host must
serialize observer/context lifetime, report outside locks and avoid recursion.
Reporting failure never alters the completed database result or authorizes retry.

**Evidence boundary:** local C/C++ adapter/sink tests are executable with available
compilers. Rust is unavailable locally, so no new real SQLite-to-observer test or
mobile/runtime transport result is claimed. The next separately authorized gate
should run real `maddb_open_memory`, put/get/remove, then this adapter, asserting
unchanged database results and expected recorded events; existing DB tests stay
unchanged. Probe+copy is two C calls, not one measured logical read. The host
chooses reporting granularity. Automatic instrumentation is not provided.

Wrapper regressions also link clearly named test-only ABI stubs, verifying exact
argument identity, one ABI call, callback ordering, caller output preservation,
all read status returns and observation failure independence. This is mock
contract execution, NOT SQLite execution. The production adapter invokes the
real symbols without replacing them. No wrapper for open/close/remove is added.

## Separate real-dispatch gate (implemented, not locally executed)

`scripts/test-obs-integration.sh` compiles the actual locked Rust library as a
dynamic library using the existing C-ABI smoke-test recipe and links `test_real.c` with no ABI stubs. It uses real in-memory
SQLite and the local recording observer: binary put/get, probe/short-buffer,
missing versus empty, observer failure independence, removal and closed-handle
rejection, with exact event counts/statuses. It performs no network or file DB IO.

The separate optional workflow stages only the exact public MadObs header via
an anonymous isolated Git fetch, checks its exact full commit and blob identity, uses the existing Rust
1.100.0/Ubuntu 24.04 recipe and locked dependencies, then runs both clearly
separated contract and real-dispatch tests. No binary/header is redistributed.
No SQLite execution has occurred locally because Cargo is unavailable. Real
dynamic linking and dispatch require the future authorized CI run; C syntax checks
are not a substitute. Existing default Linux/Android/iOS workflows are unchanged.

Header staging uses a fresh temporary repository/HOME, an empty inherited
environment, disabled global/system Git configuration, empty credential helpers
and HTTP extra headers, and disabled interactive prompting. No GITHUB_TOKEN is
passed to the second repository. Only the verified observer header is retained;
temporary fetched source objects are removed. Paths are rooted at this checkout
and quoted. Public fetch output stays in a local ignored log with fixed status.
