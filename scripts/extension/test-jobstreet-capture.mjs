// Synthetic fixtures only. No job-board login, provider API or personal data.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { randomUUID } from 'node:crypto';
import { build } from '../../apps/extension/node_modules/esbuild/lib/main.js';

const require = createRequire(new URL('../../apps/extension/package.json', import.meta.url));
const { parseHTML } = require('linkedom');
async function bundle(file, format = 'esm') {
	return (await build({ entryPoints: [fileURLToPath(new URL(`../../apps/extension/src/${file}`, import.meta.url))], bundle: true, format, write: false })).outputFiles[0].text;
}
const { extractJobstreetJob } = await import(`data:text/javascript;base64,${Buffer.from(await bundle('jobstreet.ts')).toString('base64')}`);
const id = '900000201';
const staleId = '900000202';
const title = 'Synthetic Data Platform Engineer';
const company = 'Example Testing Laboratory';
const description = 'Develop reproducible data pipelines for an imaginary testing laboratory. Design reliable data contracts, document transformations, investigate data quality, and collaborate with the research team. This fictional vacancy is solely a capture regression fixture.';
const searchUrl = `https://id.jobstreet.com/data-engineer-jobs/in-Jakarta?jobId=${id}&type=standard`;
const directUrl = `https://id.jobstreet.com/job/${id}`;
const normalize = value => value.replace(/\s+/g, ' ').trim();
let passed = 0;
function panel({ identity = id, raw = description, attrs = '', extra = '', knownRoot = true } = {}) {
	return `<section ${knownRoot ? 'data-automation="jobDetails"' : ''} ${identity ? `data-job-id="${identity}"` : ''} ${attrs}>
		<h1 data-automation="job-detail-title">${title}</h1>
		<a data-automation="job-detail-company-link">${company}</a>
		${raw === null ? '' : `<div data-automation="jobAdDetails">${raw}</div>`}${extra}</section>`;
}
function capture(html, url = searchUrl) {
	return extractJobstreetJob(parseHTML(`<html><body>${html}</body></html>`).document, url);
}
function selected(result) {
	assert.equal(result.extractor, 'jobstreet_detail');
	assert.equal(normalize(result.text), description);
	assert.equal(result.jobTitle, title);
	assert.equal(result.companyName, company);
	assert.equal(result.jobUrl, directUrl);
	assert.equal(result.truncated, false);
}
function blank(result) {
	assert.ok(result, 'recognized provider must not use whole-page fallback');
	assert.equal(result.text, '');
	assert.equal(result.extractor, 'none');
	assert.equal(result.jobTitle, undefined);
	assert.equal(result.companyName, undefined);
}
function test(name, run) {
	try { run(); passed++; } catch (error) { error.message = `${name}: ${error.message}`; throw error; }
}
test('split pane excludes list, insights, employer questions, and company profile', () => {
	selected(capture(`<h1>Search results unrelated heading</h1><main><aside>${'<h2>Wrong Recommended Job</h2><p>Wrong Company</p>'.repeat(40)}</aside>
		${panel({ extra: '<section>Unlock job insights Employer questions Company profile Report this advert Salary widget</section>' })}</main>`));
});
test('direct detail without DOM identity', () => selected(capture(panel({ identity: null }), `${directUrl}?origin=cardTitle`)));
test('bounded ancestor supplies metadata without known detail root', () => selected(capture(panel({ knownRoot: false }))));
for (const attrs of ['hidden', 'aria-hidden="true"', 'style="display:none"', 'style="visibility:hidden"', 'inert']) {
	test(`hidden stale panel ${attrs}`, () => selected(capture(panel({ identity: staleId, attrs }) + panel())));
}
test('stale ID rejected after selection change', () => blank(capture(panel({ identity: staleId }))));
test('search pane without identity fails closed', () => blank(capture(panel({ identity: null }))));
test('two visible matching panes are ambiguous', () => blank(capture(panel() + panel())));
test('no description never falls back to long main, selection or body', () => blank(capture(`<main>${description.repeat(10)}${panel({ raw: null })}</main>`)));
test('short or empty description', () => { blank(capture(panel({ raw: 'A short job.' }))); blank(capture(panel({ raw: '' }))); });
test('outer JD includes all nested rich text paragraphs', () => {
	const split = description.indexOf('Design');
	selected(capture(panel({ raw: `<div data-automation="jobAdDetailsRichText">${description.slice(0, split)}</div><p>${description.slice(split)}</p>` })));
});
test('inline markup preserves words and existing spaces', () => selected(capture(panel({ raw: description.replace('data pipelines', 'da<span>ta</span> <strong>pipelines</strong>') }))));
test('hidden controls and company widgets inside JD excluded', () => selected(capture(panel({ raw: `${description}<div hidden>Stale secret fixture</div><button>Apply</button><div data-automation="companyProfile">Unrelated company details</div>` }))));
test('collapsed description fails closed', () => blank(capture(panel({ raw: `${description}<button aria-expanded="false">Show more</button>` }))));
test('collapsed description footer outside JD fails closed', () => blank(capture(panel({ extra: '<button aria-expanded="false">Show more</button>' }))));
test('unrelated collapsed employer questions do not block full JD', () => selected(capture(panel({ extra: '<section><button aria-expanded="false">Employer questions</button></section>' }))));
test('company-specific marker takes priority over general advertiser marker', () => selected(capture(panel().replace('<h1', '<span data-automation="advertiser-name">Wrong advertiser</span><h1'))));
test('advertiser label can be a button without leaking JD controls', () => selected(capture(panel().replace(`<a data-automation="job-detail-company-link">${company}</a>`, `<button data-automation="advertiser-name">${company}</button>`))));
test('metadata in excluded profile and JD cannot override header employer', () => {
	const html = panel().replace('data-automation="job-detail-company-link"', 'data-automation="advertiser-name"')
		.replace('<h1', '<div data-automation="companyProfile"><span data-automation="advertiser-name">Unrelated profile employer</span></div><h1')
		.replace(description, `${description}<span hidden data-automation="advertiser-name">Stale JD employer</span>`);
	selected(capture(html));
});
test('matching scoped title link verifies selected search pane', () => selected(capture(panel({ identity: null }).replace(title, `<a href="/job/${id}">${title}</a>`))));
test('conflicting title link rejected even if panel ID matches', () => blank(capture(panel().replace(title, `<a href="/job/${staleId}">${title}</a>`))));
function posting(jobId, jobTitle = title, employer = company) {
	return { '@type': 'JobPosting', url: `https://id.jobstreet.com/job/${jobId}`, title: jobTitle, hiringOrganization: { name: employer }, description: 'Structured description must never replace visible JD.' };
}
test('matching graph posting verifies visible search identity without taking description', () => {
	const graph = { '@graph': [posting(staleId, 'Wrong Title', 'Wrong Company'), posting(id)] };
	selected(capture(`<script type="application/ld+json">${JSON.stringify(graph)}</script>${panel({ identity: null })}`));
});
test('matching URL but stale title or company does not verify search', () => {
	for (const data of [posting(id, 'Old title'), posting(id, title, 'Old Company'), posting(staleId)]) {
		blank(capture(`<script type="application/ld+json">${JSON.stringify(data)}</script>${panel({ identity: null })}`));
	}
});
test('structured URL must be an explicit direct posting and employer must match', () => {
	for (const url of [[], {}, '', ' ', '#description', searchUrl]) {
		blank(capture(`<script type="application/ld+json">${JSON.stringify({ ...posting(id), url })}</script>${panel({ identity: null })}`));
	}
	for (const hiringOrganization of [undefined, company, {}, { name: 123 }]) {
		blank(capture(`<script type="application/ld+json">${JSON.stringify({ ...posting(id), hiringOrganization })}</script>${panel({ identity: null })}`));
	}
	selected(capture(`<script type="application/ld+json">${JSON.stringify({ ...posting(id), url: `/job/${id}` })}</script>${panel({ identity: null })}`));
});
test('identity evidence cannot cross Jobstreet markets with the same numeric ID', () => {
	blank(capture(`<script type="application/ld+json">${JSON.stringify({ ...posting(id), url: `https://my.jobstreet.com/job/${id}` })}</script>${panel({ identity: null })}`));
	blank(capture(panel({ identity: null }).replace(title, `<a href="https://my.jobstreet.com/job/${id}">${title}</a>`)));
	selected(capture(`<script type="application/ld+json">${JSON.stringify({ ...posting(id), url: `https://www.jobstreet.co.id/job/${id}` })}</script>${panel({ identity: null })}`));
});
test('malformed structured data is ignored safely', () => selected(capture(`<script type="application/ld+json">{ invalid</script>${panel()}`)));
test('nested conflicting description ID rejected', () => blank(capture(panel().replace('data-automation="jobAdDetails"', `data-automation="jobAdDetails" data-job-id="${staleId}"`))));
test('conflicting ID on a nested visible rich text element is rejected', () => blank(capture(panel({ raw: `<div data-automation="jobAdDetailsRichText" data-job-id="${staleId}">${description}</div>` }))));
test('hidden or excluded nested IDs cannot poison the selected JD', () => {
	for (const attrs of ['hidden', 'inert', 'data-automation="companyProfile"', 'data-automation="similarJobs"']) {
		selected(capture(panel({ raw: `${description}<div data-job-id="${staleId}" ${attrs}>Unrelated stale text</div>` })));
	}
});
test('table cell and row boundaries are preserved and visible code survives', () => {
	const result = capture(panel({ raw: '<table><tr><th>Skill</th><th>Experience</th></tr><tr><td>Python</td><td>3 years</td></tr><tr><td>SQL</td><td>2 years</td></tr></table><pre><code>SELECT visible_code FROM fixtures;</code></pre><script>hidden_script_poison</script>' }));
	assert.ok(result.text.includes('Python 3 years'));
	assert.ok(result.text.includes('SQL 2 years'));
	assert.ok(result.text.includes('visible_code'));
	assert.ok(!result.text.includes('hidden_script_poison'));
});
test('legacy Indonesian host canonicalized', () => selected(capture(panel(), `https://www.jobstreet.co.id/id/job/${id}`)));
test('direct job path wins over stale selected query ID', () => selected(capture(panel(), `${directUrl}?jobId=${staleId}`)));
test('invalid, duplicated, non-ASCII and unrelated-path selected IDs fail closed', () => {
	for (const url of [`https://id.jobstreet.com/jobs?jobId=${id}&jobId=${staleId}`, 'https://id.jobstreet.com/jobs?jobId=１２３', `https://id.jobstreet.com/help?jobId=${id}`, `https://id.jobstreet.com/job/${id}extra`, 'https://id.jobstreet.com/jobs']) blank(capture(panel(), url));
});
test('regional Jobstreet host retained', () => assert.equal(capture(panel(), `https://my.jobstreet.com/job/${id}`).jobUrl, `https://my.jobstreet.com/job/${id}`));
test('lookalike and unrelated domains do not match Jobstreet', () => {
	for (const host of ['jobstreet.com.evil.test', 'notjobstreet.com', 'jobstreet.co.id.evil.test']) assert.equal(capture(panel(), `https://${host}/job/${id}`), undefined);
});

const contentCode = await bundle('content.ts', 'iife');
const backgroundCode = await bundle('background.ts', 'iife');
for (const [html, complete] of [[panel(), true], [panel({ identity: staleId }), false]]) {
	const { document, window } = parseHTML(`<html><head><title>Wrong search page title</title></head><body><main><aside>${description.repeat(8)}</aside>${html}</main></body></html>`);
	window.getSelection = () => ({ toString: () => `Unrelated selection ${description.repeat(8)}` });
	let message;
	vm.runInNewContext(contentCode, { document, window, location: new URL(searchUrl), URL, chrome: { runtime: { sendMessage: value => { message = value; } } } });
	if (complete) selected(message.payload); else blank(message.payload);
	const listeners = [];
	let body;
	vm.runInNewContext(backgroundCode, {
		URL, AbortSignal, setTimeout, clearTimeout, crypto: { randomUUID },
		fetch: async (_url, init) => { body = JSON.parse(init.body); return { ok: true, json: async () => ({ ref: 'SYNTHETIC', capture_completeness: complete ? 'CAPTURED_COMPLETE' : 'CAPTURED_PARTIAL' }) }; },
		chrome: {
			runtime: { onMessage: { addListener: fn => listeners.push(fn), removeListener: fn => listeners.splice(listeners.indexOf(fn), 1) }, getManifest: () => ({ version: 'test-only' }) },
			storage: { local: { get: async () => ({ apiBaseUrl: 'http://127.0.0.1:8001/api/v1', apiKey: 'synthetic-only' }) } },
			tabs: { query: async () => [{ id: 9, url: searchUrl, title: 'Wrong search page title' }] },
			scripting: { executeScript: async () => listeners[1](message, { tab: { id: 9 } }) }
		}
	});
	const outcome = await new Promise(resolve => listeners[0]({ type: 'CAPTURE_ACTIVE_TAB' }, {}, resolve));
	assert.equal(outcome.ok, true);
	assert.equal(body.url, directUrl);
	assert.equal(body.page_title, complete ? title : '');
	assert.equal(body.job_title, complete ? title : undefined);
	assert.equal(body.company_name, complete ? company : undefined);
	assert.equal(body.raw_text, complete ? description : undefined);
	assert.equal(body.metadata.source_page_url, searchUrl);
	assert.equal(body.metadata.original_page_title, 'Wrong search page title');
	passed++;
}
console.log(`Jobstreet capture regressions passed (${passed} synthetic cases)`);
