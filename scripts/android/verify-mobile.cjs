// Runs on an AVD through ADB. It does not use desktop viewport/device emulation.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const { execFileSync, spawn } = require('node:child_process');
const webRequire = createRequire(path.resolve('apps/web/package.json'));
const { _android: android } = webRequire('playwright');
const { expect } = webRequire('@playwright/test');

const output = process.env.ANDROID_EVIDENCE;
assert(output, 'ANDROID_EVIDENCE must name an evidence directory');
fs.mkdirSync(output, { recursive: true });
const config = Object.fromEntries(fs.readFileSync('.env.simulation', 'utf8').trim().split('\n').map(line => {
  const index = line.indexOf('=');
  return [line.slice(0, index), line.slice(index + 1)];
}));
const headers = { 'X-API-Key': config.OSCAR_API_KEY };
const origin = 'http://127.0.0.1:5173';
const report = { environment: 'Android AVD, not a physical phone', checks: [],
  os_share_target: { status: 'not-tested' }, ai: 'simulation; no provider requests' };
const adb = (...args) => execFileSync('adb', args, { encoding: 'utf8', timeout: 30000 });
const save = () => fs.writeFileSync(path.join(output, 'result.json'), JSON.stringify(report, null, 2));
async function api(resource) {
  const response = await fetch(`http://127.0.0.1:8000${resource}`, { headers });
  assert.equal(response.status, 200, resource);
  return response.json();
}
async function main() {
  assert.deepEqual(await api('/health').then(h => ({ env: h.env, db: h.db })), { env: 'simulation', db: 'ok' });
  adb('reverse', 'tcp:5173', 'tcp:5173');
  const [device] = await android.devices();
  assert(device, 'An Android emulator must be connected');
  device.setDefaultTimeout(15000);
  report.device = { model: device.model(), serial: device.serial(),
    android: adb('shell', 'getprop', 'ro.build.version.release').trim(),
    sdk: adb('shell', 'getprop', 'ro.build.version.sdk').trim(),
    chrome: adb('shell', 'dumpsys', 'package', 'com.android.chrome').match(/versionName=(\S+)/)?.[1] };
  report.device.googlePlayServices = adb('shell', 'dumpsys', 'package', 'com.google.android.gms')
    .match(/versionName=(\S+)/)?.[1] || null;
  report.device.playStorePresent = adb('shell', 'pm', 'list', 'packages', 'com.android.vending')
    .includes('package:com.android.vending');
  adb('logcat', '-c');
  assert(report.device.chrome, 'The Google APIs image must include Chrome');
  adb('shell', 'svc', 'power', 'stayon', 'true');
  // Reduce software-rendering load while retaining a phone-size Android UI.
  adb('shell', 'wm', 'size', '720x1600');
  adb('shell', 'wm', 'density', '280');
  report.device.display = '720x1600, density 280';
  const recordingLog = fs.openSync(path.join(output, 'screenrecord.log'), 'w');
  const recording = spawn('adb', ['shell', 'screenrecord', '--time-limit', '180',
    '--size', '540x1200', '--bit-rate', '2500000', '/data/local/tmp/oscar-android.mp4'],
    { stdio: ['ignore', recordingLog, recordingLog] });
  fs.closeSync(recordingLog);
  let context;
  let page;
  const shot = async name => device.screenshot({ path: path.join(output, `${name}.png`) });
  const nativeTree = async name => {
    const remote = `/data/local/tmp/oscar-${name}.xml`;
    const dumped = adb('shell', 'uiautomator', 'dump', remote);
    assert(dumped.includes('UI hierchary dumped') || dumped.includes('UI hierarchy dumped'),
      'UI Automator must produce a fresh tree');
    const xml = adb('shell', 'cat', remote);
    fs.writeFileSync(path.join(output, `${name}.xml`), xml);
    return xml;
  };
  let action = 0;
  const nativeTap = async selector => {
    // Use one UI Automator observer. Mixing its dumps with a second persistent
    // instrumentation driver can disconnect that driver's accessibility client.
    const tree = await nativeTree(`native-action-${++action}`);
    const nodes = tree.match(/<node\b[^>]*>/g) || [];
    const matches = nodes.filter(node => Object.entries(selector).every(([key, value]) =>
      node.includes(`${key === 'desc' ? 'content-desc' : key}="${value}"`)));
    assert.equal(matches.length, 1, `Native control must be unambiguous: ${JSON.stringify(selector)}`);
    const bounds = matches[0].match(/bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"/);
    assert(bounds, 'Native control must have visible bounds');
    const [, left, top, right, bottom] = bounds.map(Number);
    adb('shell', 'input', 'tap', String(Math.round((left + right) / 2)),
      String(Math.round((top + bottom) / 2)));
  };
  try {
    context = await device.launchBrowser({ viewport: null, hasTouch: true });
    page = await context.newPage();
    page.setDefaultTimeout(20000);
    await page.goto(`${origin}/jobs`);
    for (let attempt = 0; attempt < 4; attempt++) {
      const startup = await nativeTree(`00-chrome-startup-${attempt}`);
      if (startup.includes('Chrome isn\'t responding')) {
        await nativeTap({ text: 'Wait' });
      } else if (startup.includes('text="No thanks"')) {
        await nativeTap({ text: 'No thanks' });
      } else {
        break;
      }
    }
    const ready = await nativeTree('00-chrome-ready');
    assert(!ready.includes('Chrome isn\'t responding'), 'Chrome must be responsive');
    assert(!ready.includes('text="No thanks"'), 'Chrome onboarding must be dismissed');
    await expect(page.getByRole('heading', { name: 'Job Inbox', exact: true })).toBeVisible();
    report.browser = await page.evaluate(() => ({ userAgent: navigator.userAgent,
      width: innerWidth, height: innerHeight, touchPoints: navigator.maxTouchPoints,
      secureContext: isSecureContext }));
    assert.match(report.browser.userAgent, /Android/);
    assert(report.browser.touchPoints > 0);
    assert(report.browser.width < 600, 'Use the Android window, not a desktop viewport');
    await shot('01-android-inbox');

    const stamp = Date.now();
    const manualUrl = `https://example.com/jobs/android-manual-${stamp}`;
    await page.getByLabel('Job URL', { exact: true }).tap();
    await page.getByLabel('Job URL', { exact: true }).fill(manualUrl);
    await shot('02-url-and-android-keyboard');
    await page.getByRole('button', { name: 'Save job', exact: true }).tap();
    await expect(page.getByText('Saved.', { exact: true })).toBeVisible();
    const summaries = (await api('/api/v1/jobs')).items;
    const details = await Promise.all(summaries.map(job => api(`/api/v1/jobs/${job.id}`)));
    const manual = details.find(job => job.canonical_url === manualUrl);
    assert(manual, 'Android form submission must reach the database');
    assert.equal(manual.capture_completeness, 'NEEDS_ENRICHMENT');
    report.checks.push({ name: 'Android Chrome URL capture', status: 'passed', job_id: manual.id });

    // Exercise the receiver with the payload Chrome/other apps normally supply.
    // Direct navigation proves the receiver, NOT OS registration/dispatch.
    const sharedUrl = `https://example.com/jobs/android-shared-${stamp}`;
    const query = new URLSearchParams({ title: 'Android example Data Engineer',
      text: `Example vacancy shared from Android ${sharedUrl}` });
    await page.goto(`${origin}/share-target?${query}`);
    await expect(page.getByRole('heading', { name: /^Saved as J\d+/ })).toBeVisible();
    await expect(page.getByText(/Only the link was shared/)).toBeVisible();
    await shot('03-shared-payload-saved');
    await page.getByRole('link', { name: 'Open job →', exact: true }).tap();
    await expect(page.getByRole('button', { name: 'Generate CV', exact: true })).toBeDisabled();
    const sharedId = Number(new URL(page.url()).pathname.split('/').pop());
    const shared = await api(`/api/v1/jobs/${sharedId}`);
    assert.equal(shared.capture_completeness, 'CAPTURED_PARTIAL');
    assert.equal(shared.canonical_url, sharedUrl);
    assert.equal(shared.snapshots[0].capture_method, 'mobile_share');
    const description = 'Example Android test vacancy for a Data Engineer. Build Python and SQL pipelines, validate source data, document transformations, and collaborate with analysts on reliable reporting.';
    await page.getByPlaceholder('Paste the full job description here…').fill(description);
    await page.getByRole('button', { name: 'Save description', exact: true }).tap();
    await expect(page.locator('pre')).toHaveText(description);
    await expect(page.getByRole('button', { name: 'Generate CV', exact: true })).toBeEnabled();
    assert.equal((await api(`/api/v1/jobs/${sharedId}`)).capture_completeness, 'CAPTURED_COMPLETE');
    await shot('04-description-completed');
    report.checks.push({ name: 'Shared-text receiver and enrichment on Android',
      status: 'passed', job_id: sharedId, dispatch: 'direct receiver URL, not OS share' });

    await page.goto(`${origin}/share-target?text=no-link-here`);
    await expect(page.getByRole('heading', { name: "Couldn't save this job", exact: true })).toBeVisible();
    await expect(page.getByText('No URL was found in the shared content.', { exact: true })).toBeVisible();
    await shot('05-explicit-capture-error');
    await page.getByRole('link', { name: '← Job Inbox', exact: true }).tap();
    await expect(page.getByRole('heading', { name: 'Job Inbox', exact: true })).toBeVisible();
    report.checks.push({ name: 'Invalid share payload gives a recoverable error', status: 'passed' });

    const cdp = await context.newCDPSession(page);
    await cdp.send('Page.enable');
    report.installability = await cdp.send('Page.getInstallabilityErrors');
    await nativeTap({ desc: 'Customize and control Google Chrome' });
    let tree = await nativeTree('06-chrome-menu');
    const installLabel = [...tree.matchAll(/text="([^"]+)"/g)].map(match => match[1])
      .find(text => /^(Add to Home screen|Install app)$/.test(text));
    if (installLabel) {
      await nativeTap({ text: installLabel });
      tree = await nativeTree('07-install-prompt');
      await shot('07-install-prompt');
      // Installing into the disposable AVD is part of this test. A shortcut
      // alone does not establish WebAPK share registration.
      for (const label of ['Install', 'Add', 'Create shortcut']) {
        if (tree.includes(`text="${label}"`)) {
          await nativeTap({ text: label });
          break;
        }
      }
      await nativeTree('08-after-install-attempt');
      // WebAPK installation is asynchronous. A shortcut is not sufficient.
      await expect.poll(() => adb('shell', 'pm', 'list', 'packages').includes('webapk'),
        { timeout: 30000 }).toBeTruthy().catch(() => {});
      const settled = await nativeTree('08-install-settled');
      if (settled.includes('text="Add to home screen"')) {
        await nativeTap({ text: 'Add to home screen' });
        await nativeTree('08-home-screen-confirmed');
      }
    } else {
      adb('shell', 'input', 'keyevent', '4');
    }
    report.webapkPackages = adb('shell', 'pm', 'list', 'packages')
      .split('\n').filter(line => line.includes('webapk'));

    // A native Android ACTION_SEND resolver, without posting to any recipient.
    // Always record OS dispatch separately from the direct receiver check.
    // Bring the actual Chrome activity back after any launcher pin dialog.
    adb('shell', 'am', 'start', '-a', 'android.intent.action.VIEW', '-d', `${origin}/jobs`,
      '-p', 'com.android.chrome');
    await page.bringToFront();
    await page.goto(`${origin}/jobs`);
    const osShareUrl = `https://example.com/jobs/android-os-share-${stamp}`;
    await page.evaluate(url => {
      const button = document.createElement('button');
      button.textContent = 'Android OS share test';
      button.style.cssText = 'position:fixed;top:100px;left:10px;z-index:99999;background:white;padding:20px';
      button.onclick = () => navigator.share({ title: 'Example Android vacancy',
        text: 'Synthetic test vacancy', url }).catch(() => {});
      document.body.append(button);
    }, osShareUrl);
    await page.getByRole('button', { name: 'Android OS share test', exact: true }).tap();
    const shareTree = await nativeTree('09-native-android-share-picker');
    await shot('09-native-android-share-picker');
    report.shareActivity = adb('shell', 'dumpsys', 'activity', 'activities').split('\n')
      .filter(line => /topResumedActivity|mResumedActivity/.test(line)).join('\n');
    const androidResolverVisible = /ChooserActivity|ResolverActivity/.test(report.shareActivity);
    assert(androidResolverVisible, 'A native Android share dialog must actually open');
    const oscarVisible = /text="[^"]*OSCAR/.test(shareTree);
    report.os_share_target = { status: oscarVisible ? 'available-not-dispatched' : 'blocked',
      native_picker_opened: true, oscar_visible: oscarVisible,
      note: oscarVisible ? 'Target visible; capture from the OS still needs verification.' :
        'OSCAR is absent from this AVD share picker. Direct receiver tests do not prove installed-PWA dispatch. Localhost/WebAPK installation must be evaluated separately.' };
    if (oscarVisible) {
      const label = [...shareTree.matchAll(/text="([^"]*OSCAR[^"]*)"/g)][0][1];
      await nativeTap({ text: label });
      let captured;
      await expect.poll(async () => {
        const jobs = (await api('/api/v1/jobs')).items;
        const details = await Promise.all(jobs.map(job => api(`/api/v1/jobs/${job.id}`)));
        captured = details.find(job => job.canonical_url === osShareUrl);
        return !!captured;
      }, { timeout: 30000 }).toBeTruthy();
      assert.equal(captured.capture_completeness, 'CAPTURED_PARTIAL');
      assert.equal(captured.snapshots[0].capture_method, 'mobile_share');
      await shot('10-native-share-saved-in-oscar');
      const receiverTree = await nativeTree('10-native-share-saved-in-oscar');
      assert(receiverTree.includes(`Saved as ${captured.ref}`));
      report.os_share_target = { status: 'passed', native_picker_opened: true,
        oscar_visible: true, job_id: captured.id, ref: captured.ref,
        note: 'Android chooser selected OSCAR and the real receiver saved a partial job.' };
    } else {
      adb('shell', 'input', 'keyevent', '4');
    }
    report.status = 'browser-checks-passed; see separate OS-share status';
  } catch (error) {
    report.status = 'failed';
    report.failure = String(error);
    await shot('failure').catch(() => {});
    await nativeTree('failure').catch(() => {});
    throw error;
  } finally {
    save();
    try {
      const lines = adb('logcat', '-d', '-v', 'threadtime').split('\n')
        .filter(line => /webapk|webapp|finsky|PackageInstaller|PackageManager|chromium.*ERROR/i.test(line));
      fs.writeFileSync(path.join(output, 'android-install.log'), lines.join('\n'));
    } catch {}
    try { adb('shell', 'pkill', '-2', 'screenrecord'); } catch {}
    await Promise.race([
      new Promise(resolve => recording.exitCode !== null ? resolve() : recording.once('exit', resolve)),
      new Promise(resolve => { const timer = setTimeout(resolve, 10000); timer.unref(); })
    ]);
    if (recording.exitCode === null) recording.kill();
    try { adb('pull', '/data/local/tmp/oscar-android.mp4', path.join(output, 'OSCAR-Android-Emulator.mp4')); } catch {}
    report.recording_saved = fs.existsSync(path.join(output, 'OSCAR-Android-Emulator.mp4'));
    save();
    await context?.close().catch(() => {});
    await device.close().catch(() => {});
  }
  assert(report.recording_saved, 'The Android recording must be preserved');
  console.log(JSON.stringify(report, null, 2));
}
main().catch(error => { save(); console.error(error); process.exitCode = 1; });
