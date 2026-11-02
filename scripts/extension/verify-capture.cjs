const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync, spawn } = require('node:child_process');
const { chromium } = require('../../apps/web/node_modules/playwright');

const output = process.env.DEMO_OUTPUT;
const extension = path.resolve('apps/extension/dist');
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const xdo = (...args) => execFileSync('xdotool', args.map(String));
const results = [];

async function api(endpoint) {
  const response = await fetch(`http://127.0.0.1:8000/api/v1${endpoint}`, {
    headers: { 'X-API-Key': 'simulation-only-key' }
  });
  assert(response.ok, `${endpoint}: ${response.status}`);
  return response.json();
}

function screenshot(name) {
  execFileSync('ffmpeg', ['-loglevel', 'error', '-y', '-f', 'x11grab',
    '-video_size', '1280x820', '-i', process.env.DISPLAY, '-vframes', '1',
    path.join(output, name)]);
}

async function waitForJobCount(count) {
  for (let attempt = 0; attempt < 80; attempt++) {
    const { items } = await api('/jobs');
    if (items.length === count) return items[0];
    await wait(200);
  }
  throw new Error(`Expected ${count} jobs`);
}

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'oscar-quality-'));
  const context = await chromium.launchPersistentContext(profile, {
    executablePath: chromium.executablePath(), headless: false, viewport: null,
    ignoreDefaultArgs: ['--disable-extensions', '--enable-automation'],
    args: ['--no-sandbox', '--ozone-platform=x11', '--no-first-run',
      '--window-size=1280,820', '--window-position=0,0',
      `--disable-extensions-except=${extension}`, `--load-extension=${extension}`]
  });
  let recording;
  let restartedApi;
  try {
    const worker = context.serviceWorkers()[0] || await context.waitForEvent('serviceworker');
    const id = new URL(worker.url()).hostname;
    const page = context.pages()[0];
    const options = await context.newPage();
    await options.goto(`chrome-extension://${id}/options.html`);
    await options.locator('#apiKey').fill('simulation-only-key');
    await options.locator('#save').click();
    await options.getByText('Saved.', { exact: true }).waitFor();
    await page.goto('chrome://extensions/shortcuts');
    await page.evaluate(async (extensionId) => {
      await chrome.developerPrivate.updateExtensionCommand({
        extensionId, commandName: '_execute_action', keybinding: 'Alt+Shift+J'
      });
    }, id);

    let count = 0;
    async function saveNative() {
      await page.bringToFront();
      xdo('key', 'alt+shift+j');
      await wait(800);
      // Native Chrome popup position in the fixed 1280x820 runner window.
      xdo('mousemove', 950, 110);
      xdo('click', '1');
      const item = await waitForJobCount(++count);
      await wait(600);
      xdo('key', 'Escape');
      return api(`/jobs/${item.id}`);
    }

    // These synthetic pages isolate metadata formats from live-site changes.
    const fixtures = [
      { name: 'json-ld-graph', title: 'AI Engineer', company: 'Fixture Labs',
        html: '<script type="application/ld+json">{"@graph":[{"@type":["JobPosting"],"title":"AI Engineer","hiringOrganization":{"name":"Fixture Labs"}}]}</script><h1>Unrelated heading</h1>' },
      { name: 'invalid-json-microdata', title: 'Data Analyst', company: 'Fixture Analytics',
        html: '<script type="application/ld+json">invalid</script><main itemscope itemtype="https://schema.org/JobPosting"><span itemprop="title">Data Analyst</span><div itemprop="hiringOrganization" itemscope><span itemprop="name">Fixture Analytics</span></div></main>' },
      { name: 'plain-heading', title: 'Platform Engineer', company: null,
        html: '<main><h1>Platform Engineer</h1></main>' }
    ];
    for (const fixture of fixtures) {
      const url = `http://127.0.0.1:5173/fixture/${fixture.name}`;
      await page.route(url, (route) => route.fulfill({ contentType: 'text/html',
        body: `<title>Original fixture tab</title>${fixture.html}<p>${'Fixture job description. '.repeat(30)}</p>` }));
      await page.goto(url);
      const detail = await saveNative();
      assert.equal(detail.title, fixture.title);
      assert.equal(detail.company, fixture.company);
      assert.equal(detail.snapshots[0].page_title, 'Original fixture tab');
      results.push({ kind: 'synthetic-fixture', case: fixture.name, passed: true });
    }

    const log = fs.openSync(path.join(output, 'video.log'), 'w');
    recording = spawn('ffmpeg', ['-loglevel', 'error', '-y', '-f', 'x11grab',
      '-framerate', '12', '-video_size', '1280x820', '-i', process.env.DISPLAY,
      '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-pix_fmt', 'yuv420p',
      path.join(output, 'record.mkv')], { stdio: ['pipe', log, log] });
    const jobs = [
      ['Master Data Engineer', 'https://careers.fitch.group/job/Jakarta-Master-Data-Engineer/1438070533/'],
      ['Data Management Operation Lead', 'https://careers.fitch.group/job/Jakarta-Data-Management-Operation-Lead/1440867033/']
    ];
    for (const [title, url] of jobs) {
      const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
      assert.equal(response.status(), 200);
      const originalTitle = await page.title();
      const jobText = await page.locator('[itemprop="description"]').first().innerText();
      assert(jobText.length > 400);
      await page.getByRole('heading', { name: title, exact: true }).first().scrollIntoViewIfNeeded();
      await wait(800);
      const detail = await saveNative();
      assert.equal(detail.title, title);
      assert.equal(detail.company, 'Fitch Group');
      assert.equal(detail.url, url);
      assert.equal(detail.capture_completeness, 'CAPTURED_COMPLETE');
      assert.equal(detail.snapshots[0].capture_method, 'extension');
      assert.equal(detail.snapshots[0].page_title, originalTitle);
      const { raw_text: raw } = await api(`/jobs/${detail.id}/raw`);
      const normalize = (value) => value.replace(/\s+/g, ' ').trim();
      const lines = jobText.split('\n').map(normalize).filter((line) => line.length >= 35);
      assert(lines.every((line) => normalize(raw).includes(line)), 'Full live JD must survive capture');
      results.push({ kind: 'live-page', title, company: detail.company, url,
        ref: detail.ref, chars: raw.length, matched_lines: lines.length });
      screenshot(`saved-${detail.ref}.png`);
      const duplicate = await saveNative();
      assert.equal(duplicate.duplicate_of_job_id, detail.id);
      assert.notEqual(duplicate.id, detail.id);
      results.push({ case: 'repeated-save', ref: duplicate.ref, original: detail.ref, passed: true });
    }

    // Run the shipped popup script in an inactive extension page so its text
    // and button state can be asserted while the job remains the active tab.
    const popup = await context.newPage();
    await popup.goto(`chrome-extension://${id}/popup.html`);
    await options.evaluate(() => chrome.storage.local.set({ apiBaseUrl: 'http://127.0.0.1:8000/unavailable' }));
    await page.bringToFront();
    await popup.locator('#save').evaluate((button) => button.click());
    await popup.getByText('Error:', { exact: false }).waitFor();
    assert.equal(await popup.locator('#save').isEnabled(), true);
    assert.equal((await api('/jobs')).items.length, count);
    results.push({ case: 'http-error', message: await popup.locator('#status').innerText(), passed: true });
    process.kill(Number(process.env.DEMO_API_PID), 'SIGTERM');
    await wait(1000);
    await options.evaluate(() => chrome.storage.local.set({ apiBaseUrl: 'http://127.0.0.1:8000/api/v1' }));
    await popup.locator('#save').evaluate((button) => button.click());
    await popup.getByText('Cannot reach OSCAR API', { exact: false }).waitFor();
    assert.equal(await popup.locator('#save').isEnabled(), true);
    results.push({ case: 'backend-unreachable', message: await popup.locator('#status').innerText(), passed: true });
    restartedApi = spawn(path.resolve('apps/api/.venv/bin/python'), [
      'scripts/serve_simulation.py', '--database-url', process.env.DEMO_DATABASE_URL,
      '--storage-dir', path.join(output, 'pdf'), '--port', '8000'
    ], { cwd: path.resolve('apps/api'), stdio: 'ignore' });
    for (let attempt = 0; attempt < 30; attempt++) {
      const ready = await fetch('http://127.0.0.1:8000/health').catch(() => null);
      if (ready?.ok) break;
      await wait(500);
    }
    assert.equal((await api('/jobs')).items.length, count);
    await popup.locator('#save').evaluate((button) => button.click());
    await popup.getByText('Saved as', { exact: false }).waitFor();
    await waitForJobCount(++count);
    results.push({ case: 'retry-after-error', passed: true });

    await page.goto('http://127.0.0.1:5173/jobs', { waitUntil: 'networkidle' });
    await page.getByRole('link', { name: results.find((r) => r.kind === 'live-page').ref, exact: true }).click();
    await page.getByRole('heading', { name: /Master Data Engineer/ }).waitFor();
    await page.getByText('Fitch Group', { exact: true }).waitFor();
    screenshot('inbox-metadata.png');
    await wait(2000);
    fs.writeFileSync(path.join(output, 'result.json'), JSON.stringify(results, null, 2));
    console.log('PASS', JSON.stringify(results));
  } finally {
    if (recording) {
      recording.stdin.end('q\n');
      await new Promise((resolve) => recording.exitCode !== null ? resolve() : recording.once('exit', resolve));
    }
    await context.close();
    restartedApi?.kill('SIGTERM');
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
