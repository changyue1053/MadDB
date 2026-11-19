# Nonshipping Android packaged-symbol evidence

Exact public base3584aa1af153fd8983fba0136adf2719d8c79437/treea1be5b8a5aa96e84cd6957ff04284415931a440a. Additive inspection only. No ABI, linker, visibility, source, packaging/alignment checker, workflow, agreement, dependency or permission changes. No other SDK or composition experiment is an input.

Expected dynamic exports derived from public src/ffi.rs are exactly maddb_abi_version, maddb_open, maddb_open_memory, maddb_close, maddb_put, maddb_get and maddb_remove. The JNI shim dynamically registers private static C functions and exposes exactly JNI_OnLoad. Required entries must be defined GLOBAL DEFAULT FUNC; extra defined externally-visible weak/unique/global symbols fail, explicitly including sqlite3_*. Undefined imports (including weak imports) are not exports; .symtab is not treated as .dynsym. A complete declared dynamic table is required. SONAME must match each packaged filename, and dependencies must be the permitted system libraries plus libmaddb.so for the JNI shim; no RPATH/RUNPATH/TEXTREL. These are proposed expected boundaries, not observed binary facts.

Manual later invocation with already installed official tools:

    python3 android-symbol-evidence/audit.py --sdk SDK --aar LIBRARY.aar --apk SMOKE.apk

Uses only the exact preinstalled NDK28.2.13676358 llvm-readelf path, not an arbitrary PATH reader. It checks the exact two ARM64 library entries in actual AAR/APK, requires byte equality across packages, invokes the existing alignment/notice inspector unchanged, then audits temporary copies of those exact extracted bytes. No build-sidecar substitution. Each library is bounded64MiB; reader execution30s and returned output1MiB; raw output is temporary and never printed. Success and failures expose fixed categories only, never paths/symbol names. Unknown actual exports fail for review, not automatic ABI changes.

Six synthetic/source tests validate green/red tables, imports versus definitions, weak exports, static-table distinction, metadata, archive extraction and source-derived names. No actual AAR/APK, Android tool invocation, CI, runtime or co-loaded SQLite test has run in this stage. Passing evidence would demonstrate this package's dynamic boundary, not prove future multi-SDK coexistence, absence of ELF interposition effects or production runtime compatibility. No installs, remote writes, binaries or uploads.
