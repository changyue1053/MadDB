# Linux installed MadDB SDK acceptance preview

Linux x86_64 only. With Rust 1.100.0, locked crates already available, CMake 3.20+
and C/C++ toolchains installed, build a developer-local SDK:

```sh
bash scripts/install-linux-c-sdk.sh "/existing/parent/new MadDB SDK"
```

The destination must not exist. The build is locked and offline with only the
public C ABI feature. The SDK contains `include/maddb.h`, `lib/libmaddb.so`,
`lib/cmake/MadDB/MadDBConfig.cmake`, and the existing license and notices under
`share/MadDB`. It contains no source tree or sibling SDK. Any preparatory
`cargo fetch --locked` requires the existing public registry access separately.
No artifact publishing or release is included.

After moving the complete SDK, configure either project independently:

```sh
cmake -S linux-consumers/app-a -B /tmp/maddb-app-a-build \
  -DMadDB_DIR="/moved/MadDB SDK/lib/cmake/MadDB"
cmake --build /tmp/maddb-app-a-build
```

Use `find_package(MadDB CONFIG REQUIRED)` and `target_link_libraries(app PRIVATE
MadDB::MadDB)`. App A uses C11; App B uses C++17. App deployment still needs
normal shared-library resolution if it is moved after the consumer build. No
package registry distribution, cross-build ABI claim, or implicit MadObs fallback.

The automated gate moves the SDK to a path containing a space, then copies each
standalone consumer to its own directory and configures/builds with the exact
relocated package. It verifies selected config, headers and imported library,
and confirms exact runtime resolution without ambient loader overrides. Both
apps write different synthetic bytes under the same key and namespace in
separate SQLite files. Separate processes reopen each file and verify the exact
value. Each app also rejects the other value via a distinct mismatch status.
This is independent development integration, not shared-database concurrency,
OS sandbox proof, crypto, production durability, or a user schema change.

`checkpoint/maddb-linux-installed-sdk` runs the isolated GitHub Actions gate.
Existing package and platform workflows are unchanged. Local syntax/static
tests do not replace actual Rust/CMake/SQLite execution.

The separate `checkpoint/maddb-linux-lock-recovery` workflow branch runs the
original gate plus cross-process SQLite lock recovery on the same relocated
executables (no rebuild). The original branch keeps its baseline checks.
A opens a new store and seeds the original value. A separate Python stdlib
SQLite witness obtains `BEGIN IMMEDIATE` on A's file, changes one row without
committing, then holds the transaction while A reads only the original value
and receives exactly `MADDB_STORAGE_ERROR` on its attempted replacement. B
can commit and reopen its own store with the same namespace/key while A's
store remains locked. The witness rolls back and checks the original bytes;
A then uses the same still-live handle to read the original and commit a
different value. Fresh processes reopen both stores and check that their
values remain distinct. Fixed watchdogs bound synchronization and subprocess
waits; they are not latency assertions. The witness's SQL applies only to
these temporary synthetic fixtures. This checks the same installed Linux
build, not migration, crash/power-loss durability, WAL, or physical devices.
