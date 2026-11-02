# Android runtime verification

`android-emulator.yml` runs a Pixel-profile AVD (Android API 35, Google APIs,
x86_64) and Chrome **inside Android**. Playwright connects over ADB; the browser
uses the Android window (`viewport: null`) and its actual user agent. The
native controls are identified from fresh UI Automator trees and tapped through
ADB, so the test does not run two competing accessibility instrumentation drivers. The
application runs in the existing isolated Docker simulation stack. ADB forwards
the web, API and temporary private-import ports to the emulator; no public
endpoint or real career data is used.

The test records the device screen and checks URL capture, a shared-text payload
at the share receiver, partial-job enrichment, and an invalid-payload error with
navigation back to the inbox. It inspects Chrome's installability result,
attempts the visible install/home-screen action when available, and opens the
native Android share picker when the optional `probe_pwa` workflow-dispatch
input is enabled. Default runs focus on the native share-shortcut path below;
they do not count PWA registration as passed. Evidence is preserved even on failure.

`result.json` records browser checks and OS share registration separately. A
successful receiver URL is **not** proof of Android dispatch. An absent OSCAR
target is reported as blocked, even if the browser checks pass. A plain home
screen shortcut is also not proof that a WebAPK/share target is installed.

This is not a physical-phone, iOS, Tailscale/mobile-data, live-job extraction,
real AI, or real application submission test. It does not install a native OSCAR
wrapper or change the product's PWA architecture. The share menu uses only a
synthetic URL; only the local OSCAR receiver may be selected, never an external
recipient. If that receiver is registered, the test verifies the resulting
mobile-share job in the database and its success screen on Android.

The mobile payload includes a link in `text`, as Android share sources commonly
do. Completeness must count description content rather than the URL and repeated
page title. API regressions also verify that the original shared text remains
unchanged in the saved snapshot.

The same AVD also installs the official HTTP Shortcuts 4.9.0 x86_64 APK after
checking its release SHA-256. ADR-020's native share-to-HTTP prototype is tested
separately from PWA registration. Its private import is served only on loopback
and removed after the test; it is never placed in the evidence artifact. The
native path must actually save a mobile-share job and show its reference on the
Android success screen. A separate screen recording covers that native path.
