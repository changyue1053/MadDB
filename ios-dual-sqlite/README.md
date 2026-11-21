# Optional installed iOS dual SQLite fixture

This is a test-only app and one hosted XCTest. Ordinary SDK builds and existing
workflows do not reference it. It has no network, transfer engine, scheduler,
credentials, telemetry, downloader, or new package release.

| Exact public producer input | Commit | Tree | Existing independent verification |
| - | - | - | - |
| MadDB | `4274af59b0f577ddd14de0cb710f73e7f10baa65` | `5b3d00ffea99bfa0b1f81723aa7bff22b675f023` | [iOS store acceptance](https://github.com/changyue1053/MadDB/actions/runs/44638052469/job/135961624183) |
| MadMedia | `1b073a7e03870d3bf023d6f9ea752abf9cfbba99` | `e008401e5ea61b6147092f44a31534bc60eb2702` | [iOS installed Journal](https://github.com/changyue1053/MadMedia/actions/runs/44725905149/job/136263714046) |

The app-owned integration graph follows the [separately verified MadDB app
cohost pattern](https://github.com/changyue1053/MadDB/actions/runs/44760643429).
There is no dependency on that cohost's SDKs. `linkage.py` is the same
MadDB Mach-O identity check from its public cohost; the consumer checks the
delivered framework's executable sections and UUID after embed and sign.
The archive comes from the exact public test-only Journal installer, not the
full MadMedia SDK. It also contains the producer's unused standalone entropy
object; the fixture never calls it. Existing notices are preserved locally.

The two SDK stores live in distinct fresh 0700 app-private directories, both
named `store.sqlite`. MadDB uses its public Swift wrapper and bundled SQLite
hidden inside the embedded dynamic framework; the installed Journal C++
interface links into the app and imports system SQLite. The test accepts only
two distinct regular file identities by `lstat`; it never opens these files
for raw inspection or calls SQLite directly. Journal commits while MadDB is
closed; MadDB commits while Journal is closed. Reopens verify distinct exact
values, further writes and the final readback. Files are closed before cleanup.
This is a same-process sequential isolation check, not concurrent-writer,
shared-schema, migration, crash/power-loss durability, or physical-device proof.

Portable checks: `python3 -B ios-dual-sqlite/test_verify.py`. A separately
approved native run requires stock ARM64 macOS with Xcode 26.2 (17C52), already
available Rust 1.100.0 targets, locked offline dependencies, and the two
exact Git objects already accessible locally. On a disposable approved runner:

```sh
python3 -B ios-dual-sqlite/verify.py --media-repo /path/to/approved/public/MadMedia
```

No fetch, installation of tools, license action, uploads or physical device.
The command creates and deletes a fresh Simulator only on the approved runner.
Local public-equivalent reconstructions may be selected with explicit
`--db-ref` and `--media-ref`, but both full source trees are always checked.
No actual native run or workflow was included with this source-only checkpoint.
