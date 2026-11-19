# Independent iOS binary consumer

This project imports and links **only** `../../build/ios/MadDB.xcframework`.
It has no source-package, Rust source, C module, sibling project, or third-party
dependencies. The app embeds the dynamic framework; the hosted XCTest bundle
links that same binary and loads it from the host app's `Frameworks` directory.
Generate the XCFramework before opening this project. Regenerate the project with
`python3 ios/Smoke/generate_project.py` from the repository root if needed.

## Build and run (from repository root, on macOS with Xcode)

Unsigned generic-device compilation and linking, **not** a device installation:

```sh
xcodebuild -project ios/Smoke/MadDBSmoke.xcodeproj \
  -scheme MadDBSmoke -configuration Release \
  -destination 'generic/platform=iOS' \
  -derivedDataPath build/ios-smoke-device \
  ARCHS=arm64 ONLY_ACTIVE_ARCH=YES CODE_SIGNING_ALLOWED=NO build
```

Run the job-owned simulator regression suite:

```sh
bash scripts/test-ios-simulator.sh
```

The script requires an **Apple Silicon Mac**, preinstalled Xcode 26.2 (17C52)
at `/Applications/Xcode_26.2.app`, and the preinstalled iOS 26.2 simulator runtime.
It creates a temporary iPhone 16 simulator, verifies arm64, runs the tests, and
shuts down/deletes only that job-owned simulator on exit. It does not download
runtimes, accept licenses, or connect physical devices. Simulator signing is
local ad-hoc signing, without a developer account or provisioning profile.
The result bundle `build/ios/simulator-tests.xcresult` must not already exist;
archive a previous run's bundle before rerunning. Deployment target is iOS 15.
The project defaults to no signing; the simulator script overrides that setting.

## Regression coverage

- ABI version is exactly 1.
- Unicode database directory/file, namespace, and key; embedded NUL and SQL-looking key text.
- Binary bytes including zero/255, empty data distinguished from missing values.
- Persistence after explicit close/reopen; overwrite; idempotent removal.
- Two namespaces using one file; independent in-memory handles.
- Idempotent close; read/write/remove after close report `.nativeStatus(-2)`.
- Empty namespace reports `.nativeStatus(-1)`.
- Missing parent directory and invalid database contents report `.nativeStatus(-3)`.
- Invalid input database bytes remain unchanged after failed opening.
- Values larger than 16 MiB report `.valueTooLarge` without overwriting existing data.
- A closed valid database with header `user_version` patched to 99 reports
  `.nativeStatus(-4)`; the entire file remains unchanged after failed opening.
  The fixture uses Foundation `Data`, not a system SQLite dependency.

Namespaces are logical grouping, **not** security isolation. Apps should normally
use separate sandbox-owned files. Tests do not claim encryption, physical-device
execution, crash/power-loss durability, concurrent-process guarantees, or full
schema-migration coverage. Changed-during-read retries are not deterministically
exercised by this minimal public-API suite. Exact error assertions match the
current public Swift wrapper and C ABI status mappings.

## Validation status

Generated files and scheme were checked structurally in a Linux environment.
`xcodebuild`, Apple SDKs, and iOS Simulator are unavailable there, so neither
command above has been executed here. Compilation and runtime test results must
be obtained on macOS before declaring this binary consumer validated.


## Independent-store acceptance addition (hosted execution pending)

The original suite already tests file close/reopen and namespace separation.
`testIndependentApplicationSupportStoresPersistAcrossReopen` adds two explicitly
configured consumer instances under the installed host app's Application Support
container. Both use the same namespace and keys but distinct SQLite files.
Three open/close rounds verify persisted distinct binary values, missing versus
empty, one-store deletion and other-store updates without cross-contamination.
The test asserts the expected app bundle ID and imports only the packaged SDK.

This is ONE actual app-hosted test process with TWO consumer store configurations,
not two OS apps, sandbox-security proof or process-relaunch/crash durability.
No app group, entitlement, account, provisioning identity, real device or endpoint
is used. Store directories contain only synthetic data and are removed afterward.
Existing packaging and optional Obs integration remain separate and unchanged.

The simulator runner requires all ten exact named XCTest passes with zero
failures/skips using xcresult, not just xcodebuild's exit code. Raw simulator
output stays local; only fixed result labels escape. Local checks cover parser
regressions and script syntax only; Swift compilation and actual simulator
acceptance require the next authorized hosted run.
