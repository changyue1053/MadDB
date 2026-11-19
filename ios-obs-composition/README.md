# Optional installed iOS Swift DB → observer runtime composition

Based exclusively on public MadDB `3584aa1af153fd8983fba0136adf2719d8c79437`, using public MadObs `4af77ffa464a48307e5ff2d95f10b835919d205b`. No production API, core/provider, default target, existing package inspector or default dependency changes. The independent OFF workflow gates remain required at the same event SHA before ON.

## Actual shipping boundary

The released dynamic MadDB XCFramework intentionally hides C symbols. This candidate respects that: the Swift XCTest imports MadDB, uses `MadDatabase.inMemory`, `put`, `get` and `close`, and only after successful public operations forwards a typed synthetic outcome (put-success/get-present/get-missing) to an XCTest-only C bridge. It does **not** invoke or prove the optional MadDB C wrappers on iOS. The bridge never includes a MadDB C header, resolves a hidden DB symbol or accepts DB handles, keys, values, namespaces, SQL or sizes. The fresh WAL path is lifecycle setup for the observer only, never an event field.

ON builds the original DB XCFramework with its unchanged script in a detached producer, relocates it, then deletes that producer. Separately it anonymously builds/installs the pinned real MadObs static runtime for device and simulator with SDK zlib and explicit null crypto, deletes that producer and links only the installed runtime into the independent test bundle (not the App). The base project generator is executed in a disposable copy; typed project objects add the Swift test, C++ bridge and bridging header. No production project text or API is edited.

The bridge constructs only two numeric event kinds and one bounded enum attribute. A fixed allowlist privacy policy checks every received batch in a local discard sink (max 16 callbacks, 1MiB per batch, no retained bytes or endpoint). On success exactly three admissions and three drains with zero queue/WAL drops are required. All Swift calls finish before synchronous stop; policy, binding and callback state live through destroy. Early test failure attempts shutdown. If runtime stop/destroy fails, the bridge intentionally retains callback state rather than freeing potentially live storage; the test fails, never retries a consumed pointer. This is not a production lifecycle wrapper.

Unsigned device build-for-testing verifies linking only. Exactly one named test must pass on a job-owned ARM64 iOS26.2 simulator, no failures/skips. No physical device, remote telemetry, durable persistence, encryption-provider or production qualification. No Apple installation/license acceptance, credentials, artifacts, distribution or release.

## Local verification and limits

Four Linux source/project/result tests pass: unchanged base project bytes, Swift shipping API test placement, bridge isolation from hidden DB C API, and strict named result/count checks. Python syntax compilation passes. Native exact-pin syntax checking was attempted, but anonymous Git access failed DNS and the connector did not return all compatibility headers; no host-native compile or Apple build is claimed. Exact hosted compilation/linking and real runtime counts remain unverified.

The prior direct C-ABI fixture design was rejected before publication because the shipping framework hides those symbols. It is removed from the candidate; the release export gate is unchanged. This replacement is explicitly host-forwarded synthetic outcome composition, not automatic database telemetry or proof of the original C wrapper path.
