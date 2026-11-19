# Android-native preview: one ABI, one independent consumer

**Status: source candidate, Android build/runtime not yet verified.** This is the
first Android adapter for the existing C ABI, not a completed Android SDK release.

Scope: `arm64-v8a`, minimum API 26, compile/target SDK 35. Java API is directly
callable from Java or Kotlin; it does not require KMP or Obs. No network permission,
telemetry, encryption, credential handling, automatic backup or publishing is added.
The small independent `smoke-app` consumes the **versioned AAR file**, not library
source via `project()`; it has its own package/application ID and app-private data.

## Layering and contract

`MadDb.java -> registered JNI C methods -> unchanged maddb.h ABI -> Rust -> SQLite`.
JNI encodes strings using standard strict UTF-8 bytes, not modified JNI UTF-8, so
Unicode paths and embedded NUL keys retain the core contract. NUL paths are rejected.
Java byte arrays are copied before SQLite calls; no pinned Java memory is held during
blocking database operations. Native buffers are freed on every normal/error path.
Pending JNI exceptions are preserved. Core statuses become `MadDbException.status`;
null means missing and `byte[0]` means a present empty value. The adapter limits each
value to 16 MiB and retries a probe/copy size race at most three times.

Instance methods serialize against close; wrapper close is idempotent and subsequent
operations fail immediately. Core tokens remain opaque/non-reused. There is no
finalizer or Cleaner: callers must close explicitly, normally using try-with-resources.
Call from an app-owned worker, not the UI thread. Do not mutate caller byte arrays
concurrently. Errors/abort/OOM are not a crash recovery or encryption guarantee.

## Exact build inputs

- Linux x86_64 build host; JDK 17.
- Rust 1.100.0 with `aarch64-linux-android` target; unchanged Cargo.lock.
- Android NDK r28c `28.2.13676358`; API-26 Clang target.
- Android Gradle Plugin 8.7.3, Gradle 8.9 (official binary SHA-256 verified in CI).
- Android platform 35 and Build Tools 35.0.0.

There is no Gradle wrapper binary checked in and no local bootstrap installer.
Use an existing Gradle 8.9 via `GRADLE_BIN`. Build scripts fail rather than choose a
fallback ABI/toolchain. Rust builds explicitly disable defaults and select only
`c-api`, never `madobs`. Gradle/AGP build-tool transitives are resolved from their
public official repositories; complete transitive toolchain dependency locking is
not yet provided. Runtime wrapper/app have no Maven library dependencies.

With existing installed/licensed tools and `ANDROID_HOME` set:

```
cargo +1.100.0 fetch --locked --target aarch64-linux-android
GRADLE_BIN=/path/to/gradle-8.9/bin/gradle bash scripts/verify-android-build.sh
```

Run from the repository root. Outputs (ignored by Git):
- `android/maddb/build/versioned/maddb-android-0.1.0-preview.1-arm64-v8a.aar`
- `android/smoke-app/build/outputs/apk/debug/smoke-app-debug.apk`
- matching instrumentation APK under `outputs/apk/androidTest/debug/`.

The AAR includes both `libmaddb.so` and `libmaddb_jni.so`, consumer shrinker rules,
first-party MIT and exact locked upstream notices, and package version/ABI metadata.
No Maven deployment, app-store upload, release signing key, or artifact upload exists.

## Verification gates (not interchangeable)

1. **Static/local**: syntax and JNI signature checks only. Not Android execution.
2. **Cross-build/packaging**: hosted read-only `Android ARM64 build checks` builds the
   AAR, independent APK and instrumentation APK. It checks exact two-library ARM64
   contents and 16 KiB ELF LOAD alignment in both actual AAR and final APK. The final
   APK must also pass Build Tools `zipalign -c -P 16 -v 4`. Both Rust cdylib and JNI
   link explicitly for 16 KiB; NDK r28c and AGP 8.7.3 are pinned.
3. **Real ARM64 runtime**: an authorized ARM64 device or ARM64 Android emulator must
   load the packaged libraries and pass persistent binary/Unicode/empty/missing,
   remove, error-map and lifecycle tests. An x86 emulator or host JNI test cannot
   substitute. No emulator/device is used by the build-only workflow.
4. **16 KiB runtime**: confirm `adb shell getconf PAGE_SIZE` is 16384 and rerun the
   same persistent tests. ELF/ZIP alignment alone is not runtime proof.

The following explicitly installs/replaces **only the test app and its test APK** on
an already authorized target; run it only when installation is intended:

```
ANDROID_SERIAL=<authorized-arm64-target> bash scripts/test-android-device.sh
REQUIRE_16K=1 ANDROID_SERIAL=<authorized-16k-arm64-target> bash scripts/test-android-device.sh
```

No device was attached or modified during source preparation. ARM64 build, APK
alignment and Android runtime/16 KiB runtime are pending. Existing green Linux C ABI
checks validate only the host implementation, not Android JNI, Bionic, or packaging.

Primary references:
- https://developer.android.com/ndk/guides/other_build_systems
- https://doc.rust-lang.org/rustc/platform-support/android.html
- https://developer.android.com/ndk/guides/jni-tips
- https://developer.android.com/build/releases/agp-8-7-0-release-notes
- https://developer.android.com/guide/practices/page-sizes
- https://github.com/android/ndk/releases/tag/r28c
- https://services.gradle.org/distributions/gradle-8.9-bin.zip.sha256
