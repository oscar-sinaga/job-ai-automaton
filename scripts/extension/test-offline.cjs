/** Installed-extension regression checks against synthetic loopback fixtures.
 * No database, LLM, external job site, or application submission is involved.
 * This tests shipped popup/options scripts in extension tabs. With
 * EXTENSION_NATIVE_ACTION=1, a fresh Linux/Xvfb browser also invokes the native
 * extension action to grant activeTab for routed provider fixtures. No real
 * provider requests, personal browser profiles, or manifest edits are used.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || '../../apps/web/node_modules/playwright');

const root = path.resolve(__dirname, '../..');
const origin = 'http://127.0.0.1:8000';
const extension = path.resolve(process.env.EXTENSION_PATH || path.join(root, 'apps/extension/dist'));
const nativeAction = process.env.EXTENSION_NATIVE_ACTION === '1';
const results = [];
const requests = [];
const progress = (stage) => console.error(`[extension-offline] ${stage}`);
let mode = 'success';
const description = 'Synthetic engineering responsibility with verified career facts. '.repeat(12);
const selectedDescription = 'SELECTED_JD_BOUNDARY_START. Build reliable credit risk models with SQL and Python. '
  + 'Validate data quality, evaluate model performance, document reproducible experiments, and collaborate with risk stakeholders. '.repeat(6)
  + 'SELECTED_JD_BOUNDARY_END.';
const excludedText = ['RECOMMENDATION_POISON', 'COMPANY_PROFILE_POISON', 'PREMIUM_UPSELL_POISON', 'HIDDEN_STALE_POISON'];
const providerFixtures = [
  {
    name: 'linkedin-selected-detail', url: 'https://www.linkedin.com/jobs/search-results/?currentJobId=4447261149',
    expectedUrl: 'https://www.linkedin.com/jobs/view/4447261149/',
    title: 'Senior Data Scientist - Credit Risk', company: 'Selected Fixture Employer', extractor: 'linkedin_detail',
    html: `<title>RECOMMENDATION_POISON - unrelated search heading</title><main>
      <aside class="scaffold-layout__list"><article class="job-card-container"><h1>RECOMMENDATION_POISON</h1><p>Other company, other role</p></article></aside>
      <section class="jobs-search__job-details--container" data-job-id="4447261149">
        <h1 class="job-details-jobs-unified-top-card__job-title"><a href="/jobs/view/4447261149/">Senior Data Scientist - Credit Risk</a></h1>
        <div class="job-details-jobs-unified-top-card__company-name">Selected Fixture Employer</div>
        <aside class="jobs-premium-upsell">PREMIUM_UPSELL_POISON</aside>
        <article class="jobs-description"><div id="job-details">${selectedDescription}</div></article>
        <section class="jobs-company">COMPANY_PROFILE_POISON</section>
      </section>
      <section class="jobs-search__job-details--container" data-job-id="1111111111" style="display:none"><div id="job-details">HIDDEN_STALE_POISON</div></section>
    </main>`
  },
  {
    name: 'linkedin-sdui-selected-detail', url: 'https://www.linkedin.com/jobs/search-results/?currentJobId=4447261151',
    expectedUrl: 'https://www.linkedin.com/jobs/view/4447261151/',
    title: 'Research Engineering Lead', company: 'Synthetic Research Employer', extractor: 'linkedin_detail',
    html: `<title>RECOMMENDATION_POISON - unrelated search heading</title><div id="root"><main id="workspace">
      <div data-testid="lazy-column"><h1>RECOMMENDATION_POISON</h1><p>${description.repeat(3)}</p></div>
      <div data-testid="lazy-column" data-component-type="LazyColumn">
        <div><div>
          <div><a href="/company/synthetic-research/life/"><img alt=""><span>Synthetic Research Employer</span></a>
            <a href="/company/synthetic-research/life/">Synthetic Research Employer</a></div>
          <div><div data-display-contents="true"><p><a href="/jobs/view/synthetic-research-lead-4447261151/">Research Engineering Lead</a></p></div>
            <p>Fictional location and applicant information</p></div>
        </div></div>
        <div><div><p>PREMIUM_UPSELL_POISON</p></div><div></div>
          <div data-display-contents="true"><div><div>
            <div></div><div><h2>About the job</h2></div>
            <p><span data-testid="expandable-text-box" tabindex="0">${selectedDescription}<button aria-hidden="true" data-testid="expandable-text-button">… more</button></span></p>
            <hr role="presentation"><p>Benefits found in job post</p><p>BENEFITS_POISON</p>
          </div></div></div>
          <section><h2>About the company</h2><span data-testid="expandable-text-box">COMPANY_PROFILE_POISON</span></section>
        </div>
      </div>
      <section><h2>People you can reach out to</h2><p>RECOMMENDATION_POISON</p></section>
    </main></div>`
  },
  {
    name: 'jobstreet-selected-detail', url: 'https://id.jobstreet.com/id/data-scientist-jobs?jobId=95264526&type=standard',
    expectedUrl: 'https://id.jobstreet.com/job/95264526',
    title: 'Senior Data Scientist', company: 'Selected Jobstreet Employer', extractor: 'jobstreet_detail',
    html: `<title>RECOMMENDATION_POISON - search results</title><main>
      <aside><article data-automation="normalJob" data-job-id="12345678"><h1>RECOMMENDATION_POISON</h1><span data-automation="advertiser-name">Wrong Employer</span></article></aside>
      <article data-automation="jobDetails" data-job-id="95264526">
        <h1 data-automation="job-detail-title">Senior Data Scientist</h1>
        <span data-automation="advertiser-name">Selected Jobstreet Employer</span>
        <div data-automation="jobAdDetails">${selectedDescription}</div>
        <section data-automation="companyProfile">COMPANY_PROFILE_POISON</section>
        <aside>PREMIUM_UPSELL_POISON</aside>
      </article>
      <article data-automation="jobDetails" data-job-id="11111111" hidden><div data-automation="jobAdDetails">HIDDEN_STALE_POISON</div></article>
    </main>`
  },
  {
    name: 'jobstreet-direct-nearest-detail', url: 'https://id.jobstreet.com/job/95264527',
    expectedUrl: 'https://id.jobstreet.com/job/95264527',
    title: 'Machine Learning Engineer', company: 'Direct Jobstreet Employer', extractor: 'jobstreet_detail',
    html: `<title>RECOMMENDATION_POISON - unrelated browser title</title><main>
      <aside><h1>RECOMMENDATION_POISON</h1><span data-automation="advertiser-name">Wrong Employer</span></aside>
      <div><header><h1 data-automation="job-detail-title">Machine Learning Engineer</h1>
        <a data-automation="job-detail-company-link">Direct Jobstreet Employer</a></header>
        <div data-automation="jobAdDetails"><div data-automation="jobAdDetailsRichText">${selectedDescription}</div></div>
        <section data-automation="companyProfile">COMPANY_PROFILE_POISON</section>
        <aside>PREMIUM_UPSELL_POISON</aside>
      </div>
    </main>`
  },
  {
    name: 'jobstreet-stale-selected-pane', url: 'https://id.jobstreet.com/data-scientist-jobs?jobId=95264528',
    expectedUrl: 'https://id.jobstreet.com/job/95264528', partial: true, extractor: 'none',
    html: `<title>RECOMMENDATION_POISON</title><main><article data-automation="jobDetails" data-job-id="95264526">
      <h1 data-automation="job-detail-title">Stale Role</h1><span data-automation="advertiser-name">Stale Employer</span>
      <div data-automation="jobAdDetails">${selectedDescription}</div>
    </article></main>`
  },
  {
    name: 'linkedin-collapsed-description', url: 'https://www.linkedin.com/jobs/view/4447261150/',
    expectedUrl: 'https://www.linkedin.com/jobs/view/4447261150/', partial: true, extractor: 'none',
    html: `<title>RECOMMENDATION_POISON</title><main><section class="jobs-search__job-details--container" data-job-id="4447261150">
      <h1>Incomplete Role</h1><div class="jobs-description"><div id="job-details">${selectedDescription}</div>
      <button class="jobs-description__footer-button" aria-expanded="false">Show more</button></div>
    </section></main>`
  },
  {
    name: 'jobstreet-search-no-selected-id', url: 'https://id.jobstreet.com/data-scientist-jobs',
    expectedUrl: 'https://id.jobstreet.com/data-scientist-jobs', partial: true, extractor: 'none',
    html: `<title>RECOMMENDATION_POISON</title><main><article data-automation="jobDetails" data-job-id="95264526">
      <h1 data-automation="job-detail-title">Unselected Role</h1><span data-automation="advertiser-name">Unselected Employer</span>
      <div data-automation="jobAdDetails">${selectedDescription}</div>
    </article></main>`
  },
  {
    name: 'jobstreet-stale-nested-job-id', url: 'https://id.jobstreet.com/data-scientist-jobs?jobId=95264529',
    expectedUrl: 'https://id.jobstreet.com/job/95264529', partial: true, extractor: 'none',
    html: `<title>RECOMMENDATION_POISON</title><main><section data-automation="jobDetails" data-job-id="95264529">
      <h1 data-automation="job-detail-title">Stale Nested Role</h1><a data-automation="job-detail-company-link">Stale Nested Employer</a>
      <div data-automation="jobAdDetails"><div data-job-id="95264526">${selectedDescription}</div></div>
    </section></main>`
  }
];
const fixtures = [
  { name: 'jobstreet', title: 'Data Engineer', company: 'Fixture Jobstreet Employer', html:
    '<h1>Data Engineer</h1><button><span data-automation="advertiser-name">Fixture Jobstreet Employer</span></button>' },
  { name: 'kalibrr', title: 'Data Engineer', company: 'Fixture Kalibrr Employer', html:
    '<h1>Data Engineer</h1><a href="/c/example/jobs?action=Company%20Name"><h2>Fixture Kalibrr Employer</h2></a>' },
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
    res.end(JSON.stringify({ ref: `TEST-${requests.length}`, capture_completeness: capture.metadata?.page_access
      ? 'NEEDS_ENRICHMENT' : capture.raw_text?.trim().length >= 40 ? 'CAPTURED_COMPLETE' : 'CAPTURED_PARTIAL',
      duplicate_of_job_id: mode === 'duplicate' ? 'original-fixture-id' : null }));
  }
});

async function main() {
  progress('starting synthetic server and fresh browser');
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
      headless: !nativeAction,
      timeout: 30_000,
      ignoreDefaultArgs: ['--disable-extensions', ...(nativeAction ? ['--enable-automation'] : [])],
      args: ['--no-sandbox', ...(nativeAction ? ['--ozone-platform=x11', '--window-size=1280,820'] : []),
        `--disable-extensions-except=${extension}`, `--load-extension=${extension}`]
    });
    context.setDefaultTimeout(15_000);
    context.setDefaultNavigationTimeout(30_000);
    progress('browser started; waiting for installed extension worker');
    await context.route('**/*', (route) => {
      const url = new URL(route.request().url());
      const fixture = providerFixtures.find((item) => item.url === url.href);
      if (fixture) return route.fulfill({ contentType: 'text/html', body: fixture.html });
      return url.hostname === '127.0.0.1' || url.protocol === 'chrome-extension:'
        ? route.continue() : route.abort();
    });
    const worker = context.serviceWorkers()[0] || await context.waitForEvent('serviceworker', { timeout: 15_000 });
    const id = new URL(worker.url()).hostname;
    const options = await context.newPage();
    await options.goto(`chrome-extension://${id}/options.html`);
    await options.locator('#apiBaseUrl').fill(`${origin}/api/v1`);
    await options.locator('#apiKey').fill('synthetic-test-only-key');
    await options.locator('#save').click();
    await options.getByText('Saved.', { exact: true }).waitFor();
    progress('extension configured with synthetic key');
    const popup = await context.newPage();
    await popup.goto(`chrome-extension://${id}/popup.html`);
    const page = await context.newPage();
    if (nativeAction) {
      await page.goto('chrome://extensions/shortcuts');
      await page.evaluate(async (extensionId) => {
        await chrome.developerPrivate.updateExtensionCommand({
          extensionId, commandName: '_execute_action', keybinding: 'Alt+Shift+J'
        });
      }, id);
    }
    async function save(expected) {
      await page.bringToFront();
      // Keep the fixture tab active while executing the actual popup handler.
      await popup.locator('#save').evaluate((button) => button.click());
      try {
        await popup.locator('#status').filter({ hasText: expected }).waitFor();
      } catch (error) {
        throw new Error(`Expected popup status ${JSON.stringify(expected)}; got ${JSON.stringify(await popup.locator('#status').innerText())}`, { cause: error });
      }
      assert(await popup.locator('#save').isEnabled(), 'Save must re-enable after completion');
    }
    for (const fixture of fixtures) {
      progress(`localhost fixture: ${fixture.name}`);
      await page.goto(`${origin}/fixture/${fixture.name}`);
      await save(fixture.access ? 'URL saved as' : 'Saved as');
      const { headers, body } = requests.at(-1);
      assert.equal(body.job_title, fixture.title);
      assert.equal(body.company_name, fixture.company);
      assert.equal(body.page_title, fixture.access ? '' : fixture.pageTitle || 'Original fixture title');
      if (fixture.access) assert.equal(body.metadata.original_page_title, fixture.pageTitle);
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
      results.push(fixture.access ? `${fixture.name}: blocked page URL-only and neutral metadata` : `${fixture.name}: metadata and full description`);
    }
    if (nativeAction) {
      for (const fixture of providerFixtures) {
        progress(`routed provider fixture: ${fixture.name}`);
        await page.goto(fixture.url);
        await page.bringToFront();
        // The real browser action grants activeTab for this external origin.
        // Afterwards drive the shipped handler in its extension tab so status
        // and outbound requests can be asserted without coordinate clicks.
        execFileSync('xdotool', ['key', 'alt+shift+j']);
        await page.waitForTimeout(300);
        execFileSync('xdotool', ['key', 'Escape']);
        const before = requests.length;
        await save(fixture.partial ? 'Partially saved as' : 'Saved as');
        assert.equal(requests.length, before + 1);
        const { body } = requests.at(-1);
        assert.equal(body.job_title, fixture.title);
        assert.equal(body.company_name, fixture.company);
        assert.equal(body.page_title, fixture.title || '', 'Unrelated search headings must not become job titles');
        assert.equal(body.metadata.original_page_title, await page.title());
        assert.equal(body.url, fixture.expectedUrl);
        assert.equal(body.metadata.source_page_url, fixture.name === 'jobstreet-search-no-selected-id' ? undefined : fixture.url);
        assert.equal(body.metadata.extractor, fixture.extractor);
        if (fixture.partial) {
          assert.equal(body.raw_text, undefined, `${fixture.name}: uncertain description must not be sent`);
          results.push(`${fixture.name}: URL-only save with no uncertain JD or metadata`);
        } else {
          assert(body.raw_text.includes('SELECTED_JD_BOUNDARY_START.'));
          assert(body.raw_text.includes('SELECTED_JD_BOUNDARY_END.'));
          assert.equal(body.raw_text.replace(/\s+/g, ' ').trim(), selectedDescription.replace(/\s+/g, ' ').trim());
          for (const poison of excludedText) {
            assert(!body.raw_text.includes(poison), `${fixture.name}: leaked ${poison}`);
          }
          results.push(`${fixture.name}: native activeTab, selected full JD/title/company/canonical URL, excluded unrelated panels`);
        }
      }
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
      scope: nativeAction
        ? 'Unmodified installed extension; native action grants activeTab in disposable Linux/Xvfb; shipped popup handler driven in extension tab; routed synthetic provider HTML only, not live-site compatibility'
        : 'Installed extension with synthetic localhost server; provider/native activeTab tests require EXTENSION_NATIVE_ACTION=1; not live-site compatibility' }, null, 2));
  } finally {
    if (context) await context.close();
    server.closeAllConnections();
    await new Promise((resolve) => server.close(resolve));
    fs.rmSync(profile, { recursive: true, force: true });
  }
}
main().catch((error) => { console.error(error); server.close(); process.exitCode = 1; });
