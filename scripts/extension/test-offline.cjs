/** Installed-extension regression checks against synthetic loopback fixtures.
 * No database, LLM, external job site, or application submission is involved.
 * This tests shipped popup/options scripts in extension tabs, not the native
 * toolbar popup or activeTab permission grant. Fixtures use the existing
 * localhost host permission; no manifest permissions are widened for tests.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const { chromium } = require('../../apps/web/node_modules/playwright');

const root = path.resolve(__dirname, '../..');
const origin = 'http://127.0.0.1:8000';
const extension = path.join(root, 'apps/extension/dist');
const results = [];
const requests = [];
let mode = 'success';
const description = 'Synthetic engineering responsibility with verified career facts. '.repeat(12);
const fixtures = [
  { name: 'challenge', title: undefined, company: undefined, pageTitle: 'Just a moment...', access: 'challenge', html:
    '<h1>example.com</h1><p>Performing security verification. Performance and Security by Cloudflare.</p>' },
  { name: 'login', title: undefined, company: undefined, pageTitle: 'Sign in', access: 'login_required', html:
    '<h1>Sign in</h1><input type="password"><p>Please log in to continue.</p>' },
  { name: 'restricted', title: undefined, company: undefined, pageTitle: 'Access denied', access: 'restricted', html:
    '<h1>Access denied</h1><p>Your request was blocked.</p>' },
  { name: 'job-with-login-form', title: 'Security Engineer', company: undefined, html:
    '<h1>Security Engineer</h1><p>Build Cloudflare integrations and browser security tools.</p><input type="password">' },
  { name: 'json-ld', title: 'Data Engineer', company: 'Fixture Labs', html:
    '<script type="application/ld+json">{"@graph":[{"@type":["JobPosting"],"title":"Data Engineer","hiringOrganization":{"name":"Fixture Labs"}}]}</script><h1>Unrelated heading</h1>' },
  { name: 'microdata', title: 'Data Analyst', company: 'Fixture Analytics', html:
    '<script type="application/ld+json">invalid</script><div itemscope itemtype="https://schema.org/JobPosting"><span itemprop="title">Data Analyst</span><div itemprop="hiringOrganization" itemscope><span itemprop="name">Fixture Analytics</span></div></div>' },
  { name: 'linkedin', title: 'Platform Engineer', company: 'Fixture Employer', html:
    '<h1>Platform Engineer</h1><a class="topcard__org-name-link">Fixture Employer</a>' },
  { name: 'heading', title: 'Software Engineer', company: undefined, html:
    '<h1>Software Engineer</h1>' }
];
const server = http.createServer(async (req, res) => {
  if (req.method === 'GET') {
    const fixture = fixtures.find((item) => req.url === `/fixture/${item.name}`);
    if (fixture) {
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(`<title>${fixture.pageTitle || 'Original fixture title'}</title><main>${fixture.html}<p>${description}</p></main>`);
      return;
    }
  }
  if (req.method !== 'POST' || req.url !== '/api/v1/jobs/capture') {
    res.writeHead(404).end();
    return;
  }
  let body = '';
  for await (const chunk of req) body += chunk;
  const capture = JSON.parse(body);
  requests.push({ headers: req.headers, body: capture });
  if (mode === 'disconnect') { req.socket.destroy(); return; }
  if (mode === 'delayed') await new Promise((resolve) => setTimeout(resolve, 300));
  res.setHeader('Content-Type', 'application/json');
  if (mode === 'http-error') {
    res.writeHead(503).end(JSON.stringify({ message: 'Synthetic API unavailable' }));
  } else {
    res.end(JSON.stringify({ ref: `TEST-${requests.length}`, capture_completeness: capture.metadata?.page_access ? 'NEEDS_ENRICHMENT' : 'CAPTURED_COMPLETE',
      duplicate_of_job_id: mode === 'duplicate' ? 'original-fixture-id' : null }));
  }
});

async function main() {
  assert(fs.existsSync(path.join(extension, 'manifest.json')), 'Build the extension first');
  // Never attach to or terminate another process using this port.
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(8000, '127.0.0.1', resolve);
  });
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'oscar-extension-offline-'));
  let context;
  try {
    context = await chromium.launchPersistentContext(profile, {
      ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
        ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH } : { channel: 'chromium' }),
      headless: true,
      ignoreDefaultArgs: ['--disable-extensions'],
      args: [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`]
    });
    await context.route('**/*', (route) => {
      const url = new URL(route.request().url());
      return url.hostname === '127.0.0.1' || url.protocol === 'chrome-extension:'
        ? route.continue() : route.abort();
    });
    const worker = context.serviceWorkers()[0] || await context.waitForEvent('serviceworker');
    const id = new URL(worker.url()).hostname;
    const options = await context.newPage();
    await options.goto(`chrome-extension://${id}/options.html`);
    await options.locator('#apiBaseUrl').fill(`${origin}/api/v1`);
    await options.locator('#apiKey').fill('synthetic-test-only-key');
    await options.locator('#save').click();
    await options.getByText('Saved.', { exact: true }).waitFor();
    const popup = await context.newPage();
    await popup.goto(`chrome-extension://${id}/popup.html`);
    const page = await context.newPage();
    async function save(expected) {
      await page.bringToFront();
      // Keep the fixture tab active while executing the actual popup handler.
      await popup.locator('#save').evaluate((button) => button.click());
      await popup.locator('#status').filter({ hasText: expected }).waitFor();
      assert(await popup.locator('#save').isEnabled(), 'Save must re-enable after completion');
    }
    for (const fixture of fixtures) {
      await page.goto(`${origin}/fixture/${fixture.name}`);
      await save(fixture.access ? 'URL saved as' : 'Saved as');
      const { headers, body } = requests.at(-1);
      assert.equal(body.job_title, fixture.title);
      assert.equal(body.company_name, fixture.company);
      assert.equal(body.page_title, fixture.pageTitle || 'Original fixture title');
      assert.equal(body.metadata.page_access, fixture.access);
      assert.equal(body.url, `${origin}/fixture/${fixture.name}`);
      assert.equal(body.capture_method, 'extension');
      if (fixture.access) {
        assert.equal(body.raw_text, undefined, 'Blocked page text must not be submitted');
      } else {
        assert(body.raw_text.includes(description.trim()));
      }
      assert.equal(headers['x-api-key'], 'synthetic-test-only-key');
      assert(headers['idempotency-key']);
      results.push(`${fixture.name}: metadata and full description`);
    }
    await page.goto(`${origin}/fixture/heading`);
    mode = 'delayed';
    const count = requests.length;
    await page.bringToFront();
    await popup.locator('#save').evaluate((button) => { button.click(); button.click(); });
    assert(await popup.locator('#save').isDisabled());
    await popup.locator('#status').filter({ hasText: 'Saved as' }).waitFor();
    assert.equal(requests.length, count + 1, 'Double click must issue only one capture');
    results.push('repeated click while saving: one request');
    mode = 'duplicate';
    await save('possible duplicate');
    assert.equal(new Set(requests.map((r) => r.headers['idempotency-key'])).size, requests.length);
    results.push('later repeated save: duplicate warning and new idempotency key');
    mode = 'http-error';
    await save('Synthetic API unavailable');
    results.push('HTTP error: visible and retry enabled');
    mode = 'disconnect';
    await save('Cannot reach OSCAR API');
    results.push('connection failure: visible and retry enabled');
    mode = 'success';
    await save('Saved as');
    results.push('retry after connection failure: saved');
    await options.evaluate(() => chrome.storage.local.set({ apiKey: '' }));
    const beforeMissingKey = requests.length;
    await save('Set the API key');
    assert.equal(requests.length, beforeMissingKey);
    results.push('missing API key: no API request');
    console.log(JSON.stringify({ passed: results.length, checks: results,
      scope: 'Installed extension with synthetic server; not native toolbar or live provider compatibility' }, null, 2));
  } finally {
    if (context) await context.close();
    server.closeAllConnections();
    await new Promise((resolve) => server.close(resolve));
    fs.rmSync(profile, { recursive: true, force: true });
  }
}
main().catch((error) => { console.error(error); server.close(); process.exitCode = 1; });
