# iOS ARM64 binary preview (0.1.0-preview.1)

This is a source recipe for a standalone **MadDB.xcframework**, not a published or
signed release. An official Xcode framework target archives the Swift API and its statically linked SQLite/Rust core
inside each dynamic framework. Xcode generates/processes Info.plist, module interfaces
and the flat iOS resource layout; no script synthesizes or rewrites bundle metadata. No producer source is needed by consumers. The
only supported slices are iOS arm64 and Apple-silicon iOS Simulator arm64, minimum
iOS 15. Intel simulators, macOS/Catalyst, other platforms and Swift concurrency
conformance are not included. No MadObs dependency or encryption is enabled.

## API and integration

Add the generated `build/ios/MadDB.xcframework` to an app's **Frameworks, Libraries,
and Embedded Content** with **Embed & Sign**. Normal app signing is the consuming
app's responsibility. This unsigned preview makes no distribution identity claim.
The framework includes MIT and exact locked dependency notices. The copied C
header describes the internal ABI contract, but the C symbols are deliberately
hidden: Swift is this package's supported entry point.

```swift
import Foundation
import MadDB

let database = try MadDatabase(fileURL: databaseURL, namespace: "chat")
try database.put("message-1", value: Data([0, 255, 42]))
let bytes: Data? = try database.get("message-1") // nil != Data()
try database.remove("message-1")
try database.close()
```

Use a writable app-container **file URL**, not an SQLite URI. Memory databases
require `MadDatabase.inMemory()`. File paths, namespace and keys are UTF-8; keys
can include NUL. Core validation rejects invalid paths/namespaces. No path creates
an app sandbox or security boundary. App developers control backup/protection
policies and appropriate storage locations.

Calls block and serialize per object; keep them off the UI thread. No `Sendable`
conformance or async/actor API is claimed. `close()` is idempotent at the Swift
layer, and later operations return `MadDBError.nativeStatus(-2)`. Deinit is a
fallback, not a substitute for explicit lifetime management. `nativeStatus`
preserves ABI v1 failures: -1 argument, -2 handle, -3 storage, -4 schema,
-5 internal and -6 handle exhaustion. Missing data returns nil, not an error.
Values are limited to 16 MiB by this wrapper. External writers may race a get's
probe/copy; three bounded attempts can yield `changedDuringRead`, never a partial
buffer. A successful read is not a transaction spanning other operations.

## Reproduce on a prepared Apple-silicon Mac

Requires an already licensed Xcode **26.2 build 17C52** in
`/Applications/Xcode_26.2.app`, its iOS and simulator SDK **26.2**, preinstalled
**iOS 26.2** simulator runtime/iPhone16 device type, and Rust **1.100.0** with
`aarch64-apple-ios` and `aarch64-apple-ios-sim` targets. No local setup script accepts
terms, installs Apple runtimes or connects to devices.

1. Fetch exact public dependencies: `cargo +1.100.0 fetch --locked --target aarch64-apple-ios --target aarch64-apple-ios-sim`.
2. `bash scripts/build-ios.sh` builds offline, packages and inspects both variants.
   It refuses to overwrite an existing XCFramework to avoid stale slices.
3. Build `ios/Smoke/MadDBSmoke.xcodeproj`, scheme `MadDBSmoke`, generic iOS with
   `CODE_SIGNING_ALLOWED=NO`. This tests device compilation, **not device execution**.
4. `bash scripts/test-ios-simulator.sh` creates a fresh job-specific simulator and
   runs the independent app's XCTest against the packaged binary. Cleanup targets
   only that simulator UUID. Simulator ad-hoc signing needs no account/identity.

The app/test project has no source dependency on the producer and no third-party
packages. This source integration adds no workflow, artifact upload or release.

## Evidence gates, kept separate

The exact standalone producer and fixture code was validated at public
[checkpoint 4274af59](https://github.com/changyue1053/MadDB/commit/4274af59b0f577ddd14de0cb710f73e7f10baa65).
The [hosted job](https://github.com/changyue1053/MadDB/actions/runs/44638052469/job/135961624183)
built and inspected the framework slices, compiled the unsigned device consumer,
and passed ten named tests on the ARM64 iOS 26.2 Simulator. It did not execute
on a physical device. This source integration preserves that implementation and
fixture, without rerunning a macOS build or simulator. Portable inspector,
result-parser, shell and scheme checks passed on Linux.

Physical-device execution, release signing/distribution, minimum-iOS runtime,
performance, and data protection remain outside this proof. No cohost, optional
runtime, or other mobile platform is included.

## Primary references

- [Apple XCFrameworks](https://developer.apple.com/documentation/xcode/creating-a-multi-platform-binary-framework-bundle)
- [Rust iOS target support](https://doc.rust-lang.org/rustc/platform-support/apple-ios.html)
- [Cargo per-invocation crate-type override](https://doc.rust-lang.org/cargo/commands/cargo-rustc.html)
- [Official macOS 15 ARM64 runner image](https://github.com/actions/runner-images/blob/main/images/macos/macos-15-arm64-Readme.md)
- [GitHub-hosted runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [Apple framework Info.plist example (JavaScriptCore)](https://github.com/WebKit/WebKit/blob/main/Source/JavaScriptCore/Info.plist)
- [Apple CFBundleInfoDictionaryVersion](https://developer.apple.com/documentation/bundleresources/information-property-list/cfbundleinfodictionaryversion)
