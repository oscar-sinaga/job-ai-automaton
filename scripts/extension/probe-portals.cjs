const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { chromium } = require('../../apps/web/node_modules/playwright');
const output = process.env.DEMO_OUTPUT;
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const normalize = (value) => value.replace(/\s+/g, ' ').trim().toLowerCase();
const targets = [
  { portal: 'Jobstreet', url: 'https://id.jobstreet.com/job/95486670',
    title: 'Data Engineer', company: 'PT Sharing Vision Indonesia',
    markers: ['Advance dalam bahasa pemrosesan SQL', 'Spark, Hive, Impala'],
    descriptionSelector: '[data-automation="jobAdDetails"]' },
  { portal: 'Jobstreet', url: 'https://id.jobstreet.com/job/95115202',
    title: 'Data Engineer', company: 'PT. Universal Agri Bisnisindo',
    markers: ['Manage and maintain databases', 'Advanced Microsoft Excel'],
    descriptionSelector: '[data-automation="jobAdDetails"]' },
  { portal: 'LinkedIn', url: 'https://id.linkedin.com/jobs/view/data-engineer-at-pt-idstar-cipta-teknologi-idstar-4479654844',
    title: 'Data Engineer', company: 'PT IDstar Cipta Teknologi (IDstar)',
    markers: ['Perform data transformation, cleansing', 'Cloud ETL: Azure Data Factory, AWS Glue'],
    descriptionSelector: '.show-more-less-html__markup' },
  { portal: 'LinkedIn', url: 'https://id.linkedin.com/jobs/view/etl-developer-data-engineer-at-indocyber-global-teknologi-pt-4477281636',
    title: 'ETL Developer/ Data Engineer', company: 'Indocyber Global Teknologi, PT',
    markers: ['Minimum of 3-4 year', 'SQL, Python, AWS'],
    descriptionSelector: '.show-more-less-html__markup' },
  { portal: 'Kalibrr', url: 'https://www.kalibrr.id/c/pgi-data/jobs/274950/data-engineer',
    title: 'Data Engineer', company: 'PGI Data',
    markers: ['Create and maintain an optimal data architecture', 'WIlling to work in Banking'],
    descriptionSelector: '#job-description' },
  { portal: 'Kalibrr', url: 'https://www.kalibrr.id/c/metrodata/jobs/272641/data-engineer-4',
    title: 'Data Engineer', company: 'PT Metrodata Electronics, Tbk',
    markers: ['Create data sets that align with business needs', 'Build, test, and maintain database pipeline architecture'],
    descriptionSelector: '#job-description' }
];
async function api(endpoint) {
  const response = await fetch(`http://127.0.0.1:8000/api/v1${endpoint}`, {
    headers: { 'X-API-Key': 'simulation-only-key' }
  });
  assert(response.ok, `API ${endpoint}: ${response.status}`);
  return response.json();
}
function screenshot(name) {
  execFileSync('ffmpeg', ['-loglevel', 'error', '-y', '-f', 'x11grab',
    '-video_size', '1280x820', '-i', process.env.DISPLAY, '-vframes', '1', path.join(output, name)]);
}
(async () => {
  fs.mkdirSync(output, { recursive: true });
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'oscar-portals-'));
  const extension = path.resolve('apps/extension/dist');
  const context = await chromium.launchPersistentContext(profile, {
    executablePath: chromium.executablePath(), headless: false, viewport: null,
    ignoreDefaultArgs: ['--disable-extensions', '--enable-automation'],
    args: ['--no-sandbox', '--ozone-platform=x11', '--no-first-run',
      '--window-size=1280,820', '--window-position=0,0',
      `--disable-extensions-except=${extension}`, `--load-extension=${extension}`]
  });
  const results = [];
  try {
    const worker = context.serviceWorkers()[0] || await context.waitForEvent('serviceworker');
    const extensionId = new URL(worker.url()).hostname;
    const page = context.pages()[0];
    await page.goto(`chrome-extension://${extensionId}/options.html`);
    await page.locator('#apiKey').fill('simulation-only-key');
    await page.locator('#save').click();
    await page.getByText('Saved.', { exact: true }).waitFor();
    await page.goto('chrome://extensions/shortcuts');
    await page.evaluate(async (extensionId) => chrome.developerPrivate.updateExtensionCommand({
      extensionId, commandName: '_execute_action', keybinding: 'Alt+Shift+J'
    }), extensionId);
    for (const [index, target] of targets.entries()) {
      const result = { portal: target.portal, url: target.url, checked_at: new Date().toISOString() };
      try {
        const response = await page.goto(target.url, { waitUntil: 'domcontentloaded', timeout: 45000 });
        result.http_status = response?.status();
        await wait(3000);
        const more = page.locator('.show-more-less-html__button--more').first();
        if (await more.isVisible()) await more.click({ timeout: 2000 }).catch(() => {});
        await page.waitForFunction((markers) => markers.every((marker) =>
          document.body.innerText.replace(/\s+/g, ' ').toLowerCase().includes(marker.toLowerCase())),
          target.markers, { timeout: 12000 }).catch(() => {});
        result.final_url = page.url();
        result.page_title = await page.title();
        const body = await page.locator('body').innerText();
        result.visible_chars = body.length;
        result.markers_visible = target.markers.map((marker) => normalize(body).includes(normalize(marker)));
        result.closed_notice = /no longer accepting applications|tidak lagi menerima lamaran/i.test(body);
        result.headings = await page.locator('h1').allTextContents();
        screenshot(`${index + 1}-page.png`);
        if (!result.markers_visible.every(Boolean)) {
          result.status = 'page_not_readable_for_capture';
          result.visible_excerpt = body.slice(0, 1200);
          results.push(result);
          console.log('PORTAL', JSON.stringify(result));
          continue;
        }
        const previous = (await api('/jobs')).items.length;
        await page.bringToFront();
        execFileSync('xdotool', ['key', 'alt+shift+j']);
        await wait(800);
        execFileSync('xdotool', ['mousemove', '950', '110']);
        execFileSync('xdotool', ['click', '1']);
        let item;
        for (let attempt = 0; attempt < 80; attempt++) {
          const { items } = await api('/jobs');
          if (items.length > previous) { item = items[0]; break; }
          await wait(200);
        }
        screenshot(`${index + 1}-popup.png`);
        execFileSync('xdotool', ['key', 'Escape']);
        assert(item, 'Native popup must persist a job');
        const detail = await api(`/jobs/${item.id}`);
        const { raw_text: raw } = await api(`/jobs/${item.id}/raw`);
        result.saved = { ref: detail.ref, title: detail.title, company: detail.company,
          completeness: detail.capture_completeness, method: detail.snapshots[0].capture_method,
          raw_chars: raw.length };
        result.markers_captured = target.markers.map((marker) => normalize(raw).includes(normalize(marker)));
        const description = page.locator(target.descriptionSelector).first();
        if (await description.count()) {
          const text = await description.innerText();
          const lines = text.split('\n').map(normalize).filter((line) => line.length >= 35);
          result.description_lines = lines.length;
          result.matched_lines = lines.filter((line) => normalize(raw).includes(line)).length;
        }
        result.title_matches = normalize(detail.title || '') === normalize(target.title);
        result.company_matches = normalize(detail.company || '') === normalize(target.company);
        result.status = result.markers_captured.every(Boolean) && result.title_matches && result.company_matches
          ? 'capture_verified' : 'capture_quality_issue';
      } catch (error) {
        result.status = 'error';
        result.error = error.message;
        screenshot(`${index + 1}-error.png`);
      }
      results.push(result);
      console.log('PORTAL', JSON.stringify(result));
      fs.writeFileSync(path.join(output, 'portal-results.json'), JSON.stringify(results, null, 2));
      await wait(1500);
    }
    assert.equal(results.length, targets.length);
    fs.writeFileSync(path.join(output, 'portal-results.json'), JSON.stringify(results, null, 2));
    console.log('PROBE COMPLETED', results.map((result) => `${result.portal}: ${result.status}`).join(' | '));
  } finally {
    await context.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
