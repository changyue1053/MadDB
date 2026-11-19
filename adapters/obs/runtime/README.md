# Separate real runtime composition candidate

Explicit `MADDB_WITH_MADOBS_RUNTIME=ON` is required by the runner and consumer
CMake project. Default SDK/build targets remain untouched. This uses exact public
MadObs `4af77ffa464a48307e5ff2d95f10b835919d205b`, anonymous isolated Git staging,
static runtime installation, shared/JNI/tests/BoringSSL packaging OFF and empty
provider paths. Requires existing official runner tools/zlib; installs nothing.

Contract check: MadObs generic events accept uint32 SDK/version/event IDs, <=8
attributes, severity <=5 and reserved zero. Our fixed preview ID `0x4D444201`,
version 1, get/put event IDs 1/2, status values 0..8, severity 1/3 and zero timing
satisfy that contract. A matching finite privacy policy checks emitted batches.
No arbitrary caller IDs, data, paths or exact event clock are accepted.

The consumer links only installed MadObs runtime and a staged actual MadDB shared
library/header/adapter. Only the MadObs producer source/build trees are removed before consumer
configuration. The MadDB checkout and Rust build remain locally present; the
consumer links the staged MadDB library, not a producer-removal isolation proof. Three real SQLite operations emit through the runtime observer;
assert exact admission/drain counts, zero queue/WAL drops and a nonempty bounded
local sink. The sink checks complete policy-safe batches, retains no bytes and
acknowledges local discard only. This is not network delivery, transport privacy,
restart durability, encryption, mobile execution or a performance claim. Runtime
batch headers may contain its own timestamps; only event clock is zero. Synthetic
WAL is temporary and deleted after execution. No artifacts/dependencies published.

Locally only C++ syntax and runner/workflow static checks can run; Cargo and CMake
are absent. Hosted real execution is pending. Existing callback-only real SQLite
and mock contract gates remain separate. No upstream source changes or relicensing.

The imported MadDB `.so` has no assumed SONAME. The consumer declares
`IMPORTED_NO_SONAME TRUE` so CMake uses library search/link form instead of
encoding an absolute producer filename as DT_NEEDED, with the staged library
folder in BUILD_RPATH. The dependency check still requires exactly one
`libmaddb.so =>` resolution at the expected absolute staging path; direct-path,
missing, duplicate, different, unresolved and forbidden dependencies fail with
separate fixed labels. Both inspection and execution clear LD_LIBRARY_PATH,
LD_PRELOAD and LD_AUDIT. This is not permission for an ambient library fallback.
