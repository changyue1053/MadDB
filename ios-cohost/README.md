# Installed, app-owned iOS SDK cohost

This is one sample app, not a new SDK. ON and OFF run the same named XCTest on
separate fresh ARM64 iOS Simulator jobs. The test bundle calls only the
sample app's one-shot ingress; the ordinary UI button calls the same ingress.
The app owns the Swift database, tracked Link handle, nonblocking synthetic
transport and, in ON, one raw MadObs runtime. No SDK links to either sibling.

| Producer | Public source | Exact source tree |
| --- | --- | --- |
| MadDB | `b60392d56be3ef3f7fd1db2c9547e98a535aa0d1` | `b231055e5421f64cf5063e21088fab1dcc35006f` |
| MadLink | `80c9d8ffd23a5911b4f2eb71b5408b1d57717f2a` | `d2fd4ed05b6bd29d65b3011a6febce99dc912a4a` |
| MadObs, ON only | `af06c481226fe9abddae5218e022f52683784e3e` | `4ac71eee165885687a8a4c90ebfaf85a00b098a7` |

The separate producer trees are deleted before consumer generation. The
entire XCFrameworks move to spaced paths; the app embeds only the actual
dynamic Swift MadDB slice (its UUID and executable sections must match the
relocated package). The two static archives are explicit relocated link inputs,
not embedded or dynamically loaded. OFF neither fetches nor stages MadObs,
does not create its directory, and has no MadObs definitions or load.
No source header outside an installed package is exposed as an SDK interface.

### Scenario and observation semantics

1. The real `MadDatabase` Swift class opens a fresh app-local SQLite file,
   puts and gets a fixed value. The actual public tracked Link C ABI reports
   one local acceptance, not a delivery or business acknowledgment.
2. The app closes the input database and requires a second local Link
   acceptance. It reopens the same database, closes/destroys Link, then
   verifies the real Swift read and removal.
3. ON maps only three successful actual DB outcomes and three actual enumerated
   Link state events. No raw handle, payload, endpoint, namespace, key, path,
   timestamp, arbitrary attributes or DB C types are reported. Link tracking
   and observations are distinct: the latter use the actual finite state
   transitions, not synthetic copies of terminal delivery status.
4. The app sanitizes before raw MadObs admission and requires both per-source
   counts, six exact admissions/drains, no drops, and policy-valid bounded
   discard batches; it never forwards/stores/displays batch data. A successful
   Swift remove attempts a distinct excluded event and is rejected by the
   sanitizer before raw admission. This is an app policy, not the Linux
   owning private C binding: no `madobs/private.h` or hidden DB API is used.
   It does not prove per-event export acknowledgments or restart privacy.
5. Producers stop before the runtime. If native shutdown cannot guarantee
   callback safety, the app retains state until process teardown and returns
   failure, without retrying or accumulating more work.

The opt-in workflow uses stock Xcode 26.2 (17C52) and iOS 26.2, existing reviewed
Rust preparation, and only exact public Git receipts. Package bytes and actual
host/test executable paths, symbols, architecture, and result names are checked.
Only the job-owned simulator runs. No device, installed-owner Mac changes,
downloaded Apple SDK, license action, network traffic from the sample,
credentials, payload export, artifact upload, parity or release claim.
