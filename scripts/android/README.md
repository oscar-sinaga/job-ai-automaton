# Android runtime verification

`android-emulator.yml` runs a Pixel-profile AVD (Android API 35, Google APIs,
x86_64) and Chrome **inside Android**. Playwright connects over ADB; the browser
uses the Android window (`viewport: null`) and its actual user agent. The
application runs in the existing isolated Docker simulation stack. ADB reverses
only the web port to the emulator; no public endpoint or real career data is used.

The test records the device screen and checks URL capture, a shared-text payload
at the share receiver, partial-job enrichment, and an invalid-payload error with
navigation back to the inbox. It inspects Chrome's installability result,
attempts the visible install/home-screen action when available, and opens the
native Android share picker. Evidence is preserved even on failure.

`result.json` records browser checks and OS share registration separately. A
successful receiver URL is **not** proof of Android dispatch. An absent OSCAR
target is reported as blocked, even if the browser checks pass. A plain home
screen shortcut is also not proof that a WebAPK/share target is installed.

This is not a physical-phone, iOS, Tailscale/mobile-data, live-job extraction,
real AI, or real application submission test. It does not install a native OSCAR
wrapper or change the product's PWA architecture. The share menu uses only a
synthetic URL and no recipient is selected.
