// Synthetic DOM regressions only: no browser, network, credentials or user data.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { randomUUID } from 'node:crypto';
import { build } from '../../apps/extension/node_modules/esbuild/lib/main.js';

const require = createRequire(new URL('../../apps/extension/package.json', import.meta.url));
const { parseHTML } = require('linkedom');
const bundle = await build({
	entryPoints: [fileURLToPath(new URL('../../apps/extension/src/linkedin.ts', import.meta.url))],
	bundle: true,
	format: 'esm',
	write: false
});
const { extractLinkedInJob } = await import(
	`data:text/javascript;base64,${Buffer.from(bundle.outputFiles[0].text).toString('base64')}`
);

const selectedId = '900000101';
const staleId = '900000102';
const selectedTitle = 'Synthetic Research Lead';
const selectedCompany = 'Example Research Laboratory';
const description = [
	'Build reliable forecasting tools for an imaginary research team.',
	'Design reproducible experiments, evaluate models, and explain findings clearly.',
	'Collaborate with engineers to maintain documented data pipelines.',
	'Candidates should demonstrate statistical reasoning and thoughtful communication.',
	'Use fictional sample datasets to investigate model quality and practical limitations.',
	'Share experiment results with the team and improve the research process over time.',
	'This synthetic vacancy exists solely to exercise extraction behavior.'
].join(' ');
const pageUrl = `https://www.linkedin.com/jobs/search-results/?currentJobId=${selectedId}&trackingId=synthetic`;
const normalize = value => value.replace(/\s+/g, ' ').trim();
let passed = 0;

function capture(html, url = pageUrl) {
	const { document } = parseHTML(`<!doctype html><html><body>${html}</body></html>`);
	return extractLinkedInJob(document, url);
}

function selectedPanel({ id = selectedId, text = description, attributes = '', extra = '' } = {}) {
	return `<section class="jobs-search__job-details--container" data-job-id="${id}" ${attributes}>
		<h1>${selectedTitle}</h1>
		<div class="job-details-jobs-unified-top-card__company-name">${selectedCompany}</div>
		${text === null ? '' : `<div id="job-details">${text}</div>`}
		${extra}
	</section>`;
}

// Mirrors the live SDUI structure using only fictional jobs and text. Generated
// classes, private account markup and the saved page itself are not fixtures.
function sduiPanel({ id = selectedId, text = description, attributes = '', headerExtra = '', descriptionBlock } = {}) {
	return `<div data-testid="lazy-column" data-component-type="LazyColumn" ${attributes}>
		<div><div>
			<div><a href="/company/example-research/life/"><img alt=""><span>${selectedCompany}</span></a>
				<a href="/company/example-research/life/">${selectedCompany}</a></div>
			<div><div data-display-contents="true"><p><a href="/jobs/view/synthetic-research-lead-${id}/">${selectedTitle}</a></p></div>
				<p>Fictional location and applicant information</p>${headerExtra}</div>
		</div></div>
		<div><div><p>Premium subscription promotion</p></div><div></div>
			<div data-display-contents="true"><div><div>
				<div></div><div><h2>About the job</h2></div>
				${descriptionBlock ?? `<p><span data-testid="expandable-text-box" tabindex="0">${text}<button aria-hidden="true" data-testid="expandable-text-button">… more</button></span></p>`}
				<hr role="presentation"><p>Benefits found in job post</p><p>Unrelated fictional benefit</p>
			</div></div></div>
			<section><h2>About the company</h2><span data-testid="expandable-text-box">Unrelated company marketing</span></section>
		</div>
	</div>`;
}

function expectSelected(result, { title = selectedTitle, company = selectedCompany, id = selectedId } = {}) {
	assert.ok(result, 'LinkedIn job page must return a capture decision');
	assert.equal(result.extractor, 'linkedin_detail');
	assert.equal(result.truncated, false);
	assert.equal(normalize(result.text), description, 'capture must contain only the selected description');
	assert.equal(result.jobTitle, title, 'title must come from the selected detail pane');
	assert.equal(result.companyName, company, 'company must come from the selected detail pane');
	assert.equal(new URL(result.jobUrl).pathname.replace(/\/$/, ''), `/jobs/view/${id}`);
	assert.equal(new URL(result.jobUrl).search, '', 'canonical job URL must omit search-page tracking');
}

function expectBlank(result) {
	assert.ok(result, 'recognized LinkedIn job pages must not use generic extraction');
	assert.equal(result.text, '');
	assert.equal(result.extractor, 'none');
	assert.equal(result.truncated, false);
}

function test(name, run) {
	try {
		run();
		passed += 1;
	} catch (error) {
		error.message = `${name}: ${error.message}`;
		throw error;
	}
}

test('split-pane capture excludes recommendations and unrelated global metadata', () => {
	const cards = Array.from({ length: 24 }, (_, index) =>
		`<li><h2>Recommended Synthetic Job ${index}</h2><p>Unrelated Recommendation Company ${index}</p><p>${'Recommendation sidebar text. '.repeat(10)}</p></li>`
	).join('');
	const result = capture(`
		<h1>Global Page Heading That Is Not The Job</h1>
		<script type="application/ld+json">${JSON.stringify({
			'@type': 'JobPosting',
			title: 'Wrong Global Structured Job',
			hiringOrganization: { name: 'Wrong Global Structured Company' }
		})}</script>
		<main>
			<aside><h2>More jobs for you</h2><ul>${cards}</ul></aside>
			${selectedPanel({ extra: `
				<aside>Premium subscription promotion</aside>
				<section><h2>People you can reach out to</h2><p>Unrelated synthetic contact</p></section>
				<section><h2>About the company</h2><p>Unrelated company description</p></section>` })}
		</main>`);
	expectSelected(result);
	for (const noise of ['Recommended', 'Recommendation', 'Premium', 'People', 'contact', 'About the company', 'Global']) {
		assert.ok(!result.text.includes(noise), `capture leaked unrelated page text: ${noise}`);
	}
});

for (const [name, attributes] of [
	['hidden attribute', 'hidden'],
	['ARIA-hidden panel', 'aria-hidden="true"'],
	['display-none panel', 'style="display: none"'],
	['visibility-hidden panel', 'style="visibility: hidden"']
]) {
	test(`ignore stale detail with ${name}`, () => {
		const stale = selectedPanel({ id: staleId, text: 'Stale description that must never be captured. '.repeat(15), attributes });
		expectSelected(capture(stale + selectedPanel()));
	});
}

test('ignore stale detail under a hidden ancestor', () => {
	expectSelected(capture(`<div hidden>${selectedPanel({ id: staleId })}</div>${selectedPanel()}`));
});

test('URL and visible detail identity mismatch fails closed', () => {
	expectBlank(capture(selectedPanel({ id: staleId })));
});

test('a conflicting description ID is not overridden by the panel ID', () => {
	expectBlank(capture(selectedPanel().replace('<div id="job-details">', `<div id="job-details" data-job-id="${staleId}">`)));
});

test('conflicting title URL and panel identity fail closed', () => {
	expectBlank(capture(selectedPanel().replace(`<h1>${selectedTitle}</h1>`, `<h1><a href="/jobs/view/${staleId}/">${selectedTitle}</a></h1>`)));
});

test('hidden stale metadata cannot hide a visible selected heading', () => {
	expectSelected(capture(selectedPanel().replace(`<h1>${selectedTitle}</h1>`, `<h1 hidden>Stale hidden title</h1><h1>${selectedTitle}</h1>`)));
});

test('semantic job title and company selectors outrank earlier generic or legacy metadata', () => {
	const panel = selectedPanel()
		.replace(`<h1>${selectedTitle}</h1>`, `<h1>Search Banner</h1><div class="jobs-unified-top-card__job-title">Legacy Heading</div><h2 class="job-details-jobs-unified-top-card__job-title">${selectedTitle}</h2>`)
		.replace(`<div class="job-details-jobs-unified-top-card__company-name">`, '<a class="topcard__org-name-link">Legacy Company</a><div class="job-details-jobs-unified-top-card__company-name">');
	expectSelected(capture(panel));
});

test('recommendation metadata and description nodes inside a detail pane are ignored', () => {
	const extra = `<section class="jobs-similar-jobs"><h1><a href="/jobs/view/${staleId}/">Recommended Synthetic Job</a></h1>
		<div data-job-description data-job-id="${staleId}">${description}</div></section>`;
	expectSelected(capture(selectedPanel({ extra })));
});

test('authoritative description preserves outer text around nested generic partial markup', () => {
	const cut = description.indexOf('Collaborate');
	const text = `${description.slice(0, cut)}<div class="show-more-less-html__markup">${description.slice(cut)}</div>`;
	expectSelected(capture(selectedPanel({ text })));
});

test('inline formatting inside a word does not introduce spaces into description text', () => {
	const cut = description.indexOf('statistical') + 4;
	const text = `${description.slice(0, cut)}<strong>${description.slice(cut)}</strong>`;
	expectSelected(capture(selectedPanel({ text })));
});

test('equal-priority nested description wrappers preserve complete outer text', () => {
	const cut = description.indexOf('Collaborate');
	const panel = selectedPanel({ text: null, extra: `<div class="jobs-description-content__text">${description.slice(0, cut)}
		<div class="jobs-description-content__text">${description.slice(cut)}</div></div>` });
	expectSelected(capture(panel));
});

test('hidden nested stale description and identity do not replace the selected text', () => {
	const text = `${description}<div hidden class="show-more-less-html__markup" data-job-id="${staleId}">Hidden stale description</div>`;
	expectSelected(capture(selectedPanel({ text })));
});

test('visible nested conflicting description identity fails closed', () => {
	const text = `${description}<div class="show-more-less-html__markup" data-job-id="${staleId}">Stale nested job content</div>`;
	expectBlank(capture(selectedPanel({ text })));
});

test('missing selected description fails closed', () => {
	expectBlank(capture(`<main>${selectedPanel({ text: null })}<aside>${description}</aside></main>`));
});

test('short selected description fails closed', () => {
	expectBlank(capture(selectedPanel({ text: 'A short synthetic description.' })));
});

test('collapsed show-more description fails closed', () => {
	const html = `<section class="jobs-search__job-details--container" data-job-id="${selectedId}">
		<h1>${selectedTitle}</h1>
		<div class="job-details-jobs-unified-top-card__company-name">${selectedCompany}</div>
		<div class="jobs-description__content jobs-description__content--condensed">
			<div id="job-details">${description}</div>
			<button class="jobs-description__footer-button" aria-expanded="false">Show more</button>
		</div>
	</section>`;
	expectBlank(capture(html));
});

test('show-more footer outside the content wrapper still fails closed', () => {
	const panel = `<section class="jobs-search__job-details--container" data-job-id="${selectedId}">
		<h1>${selectedTitle}</h1><div class="jobs-description">
		<div class="jobs-description__content"><div id="job-details">${description}</div></div>
		<button class="jobs-description__footer-button" aria-expanded="false">See more</button>
		</div></section>`;
	expectBlank(capture(panel));
});

test('public LinkedIn detail extracts its description and scoped top-card metadata', () => {
	const publicId = '900000103';
	const result = capture(`
		<h1>Unrelated Global Heading</h1>
		<main class="jobs-details">
			<div class="top-card-layout">
				<h1 class="top-card-layout__title">Synthetic Public Researcher</h1>
				<a class="topcard__org-name-link">Example Public Laboratory</a>
			</div>
			<div class="show-more-less-html__markup">${description}</div>
			<aside>Premium and related jobs should stay outside the capture</aside>
		</main>`, `https://www.linkedin.com/jobs/view/${publicId}/?trk=synthetic`);
	expectSelected(result, { title: 'Synthetic Public Researcher', company: 'Example Public Laboratory', id: publicId });
});

test('public Show more without ARIA state still fails closed', () => {
	expectBlank(capture(selectedPanel({ extra: '<button class="show-more-less-html__button--more">Show more</button>' })));
});

test('recognized LinkedIn job page does not fall back to generic main or body text', () => {
	expectBlank(capture(`<main><h1>More jobs for you</h1><p>${description.repeat(4)}</p></main>`));
});

test('other hosts remain eligible for the existing generic extractor', () => {
	const html = selectedPanel();
	for (const url of [
		`https://jobs.example.test/jobs/view/${selectedId}`,
		`https://linkedin.com.example.test/jobs/view/${selectedId}`,
		`https://notlinkedin.com/jobs/view/${selectedId}`
	]) {
		assert.equal(capture(html, url), undefined, `must not classify ${url} as LinkedIn`);
	}
});

test('two visible unidentifiable detail panes are ambiguous', () => {
	expectBlank(capture(selectedPanel().replace(/ data-job-id="[^"]+"/, '') + selectedPanel().replace(/ data-job-id="[^"]+"/, '')));
});

test('search URL switched before an unidentifiable stale pane updates fails closed', () => {
	expectBlank(capture(selectedPanel().replace(/ data-job-id="[^"]+"/, '')));
});

test('matching selected title link identifies a search pane without data attributes', () => {
	const panel = selectedPanel().replace(/ data-job-id="[^"]+"/, '')
		.replace(`<h1>${selectedTitle}</h1>`, `<h1 class="job-details-jobs-unified-top-card__job-title"><a href="/jobs/view/synthetic-research-lead-${selectedId}/">${selectedTitle}</a></h1>`);
	expectSelected(capture(panel));
});

test('external title links cannot establish selected LinkedIn search identity', () => {
	const panel = selectedPanel().replace(/ data-job-id="[^"]+"/, '')
		.replace(`<h1>${selectedTitle}</h1>`, `<h1><a href="https://linkedin.com.example.test/jobs/view/${selectedId}/">${selectedTitle}</a></h1>`);
	expectBlank(capture(panel));
});

test('a direct public job URL can identify a single bounded pane without DOM identity', () => {
	expectSelected(capture(selectedPanel().replace(/ data-job-id="[^"]+"/, ''),
		`https://www.linkedin.com/jobs/view/synthetic-research-lead-${selectedId}/?trk=synthetic`));
});

test('a description without a known detail scope cannot borrow page metadata', () => {
	const result = capture(`<main><h1>Wrong Page Title</h1><div id="job-details">${description}</div></main>`,
		`https://www.linkedin.com/jobs/view/${selectedId}/`);
	assert.equal(normalize(result.text), description);
	assert.equal(result.jobTitle, undefined);
	assert.equal(result.companyName, undefined);
});

test('description section headings cannot become the job title', () => {
	const text = `<h1>About the role</h1>${description}`;
	const panel = selectedPanel({ text }).replace(`<h1>${selectedTitle}</h1>`, '');
	const result = capture(panel);
	assert.equal(result.jobTitle, undefined);
	assert.equal(normalize(result.text), `About the role ${description}`);
});

test('invalid or ambiguous selected IDs never produce mixed text', () => {
	for (const query of ['currentJobId=wrong', `currentJobId=${selectedId}&currentJobId=${staleId}`]) {
		expectBlank(capture(selectedPanel(), `https://www.linkedin.com/jobs/search-results/?${query}`));
	}
});

test('SDUI captures its heading-bounded description and linked header metadata', () => {
	const result = capture(`<div id="root"><main id="workspace">
		<div data-testid="lazy-column"><h1>More jobs for you</h1><p>${description.repeat(5)}</p></div>
		${sduiPanel()}
		<section><h2>People you can reach out to</h2><p>Unrelated fictional contact</p></section>
	</main></div>`);
	expectSelected(result);
	for (const noise of ['Premium', 'Benefits found', 'fictional benefit', 'About the company', 'marketing', 'People', '… more']) {
		assert.ok(!result.text.includes(noise), `SDUI capture leaked unrelated text: ${noise}`);
	}
});

test('SDUI inline formatting and list content stay inside the description box', () => {
	const cut = description.indexOf('Collaborate');
	const text = `<strong>${description.slice(0, cut)}</strong><ul><li>${description.slice(cut)}</li></ul>`;
	expectSelected(capture(sduiPanel({ text })));
});

test('SDUI job description headings are captured without admitting neighboring sections', () => {
	const result = capture(sduiPanel({ text: `<h3>Research responsibilities</h3>${description}` }));
	assert.equal(result.extractor, 'linkedin_detail');
	assert.equal(normalize(result.text), `Research responsibilities ${description}`);
	assert.ok(!result.text.includes('Benefits found'));
});

test('SDUI component identity works without the test ID or generated classes', () => {
	expectSelected(capture(sduiPanel().replace('data-testid="lazy-column" ', '')));
});

test('SDUI ignores stale hidden and non-selected columns', () => {
	expectSelected(capture(sduiPanel({ id: staleId, attributes: 'hidden' })
		+ sduiPanel({ id: staleId }) + sduiPanel()));
});

test('SDUI URL and title identity mismatch fails closed', () => {
	expectBlank(capture(sduiPanel({ id: staleId })));
});

test('SDUI conflicting header job links cannot be mistaken for the selected panel', () => {
	expectBlank(capture(sduiPanel({ headerExtra: `<a href="/jobs/view/${staleId}/">Stale synthetic title</a>` })));
});

test('SDUI external title link cannot establish selected job identity', () => {
	expectBlank(capture(sduiPanel().replace(`/jobs/view/synthetic-research-lead-${selectedId}/`,
		`https://linkedin.com.example.test/jobs/view/${selectedId}/`)));
});

test('SDUI missing description cannot borrow a later company expandable box', () => {
	expectBlank(capture(sduiPanel({ descriptionBlock: '<p>Description is still loading</p>' })));
});

test('SDUI description boundary with multiple expandable boxes is ambiguous', () => {
	expectBlank(capture(sduiPanel({ descriptionBlock: `<div><span data-testid="expandable-text-box">${description}</span>
		<span data-testid="expandable-text-box">Another unrelated synthetic box</span></div>` })));
});

test('SDUI a new heading outside the description box is not an acceptable boundary', () => {
	expectBlank(capture(sduiPanel({ descriptionBlock: `<section><h2>About the company</h2>
		<span data-testid="expandable-text-box">${description}</span></section>` })));
});

test('SDUI nearest column cannot borrow a selected title from an outer column', () => {
	const unidentifiable = sduiPanel().replace(`<a href="/jobs/view/synthetic-research-lead-${selectedId}/">${selectedTitle}</a>`, selectedTitle);
	expectBlank(capture(`<div data-testid="lazy-column"><p><a href="/jobs/view/${selectedId}/">${selectedTitle}</a></p>${unidentifiable}</div>`));
});

test('two visible SDUI selected detail columns are ambiguous', () => {
	expectBlank(capture(sduiPanel() + sduiPanel()));
});

test('SDUI explicit collapsed state still requires the full description', () => {
	expectBlank(capture(sduiPanel({ descriptionBlock: `<p><span data-testid="expandable-text-box">${description}
		<button aria-expanded="false">See more</button></span></p>` })));
});

test('SDUI unrelated collapsed widgets do not block the selected description', () => {
	const panel = sduiPanel().replace('Unrelated company marketing</span>',
		'Unrelated company marketing</span><button aria-expanded="false">See more</button>');
	expectSelected(capture(panel));
});

test('SDUI ambiguous header employers cannot borrow metadata from a later widget', () => {
	const panel = sduiPanel({ headerExtra: '<a href="/company/another-fictional-employer/life/">Another fictional employer</a>' })
		.replace('Unrelated company marketing</span>',
			'Unrelated company marketing</span><a class="topcard__org-name-link">Unrelated metadata employer</a>');
	const result = capture(panel);
	assert.equal(result.extractor, 'linkedin_detail');
	assert.equal(normalize(result.text), description);
	assert.equal(result.jobTitle, selectedTitle);
	assert.equal(result.companyName, undefined);
});

const contentBundle = await build({
	entryPoints: [fileURLToPath(new URL('../../apps/extension/src/content.ts', import.meta.url))],
	bundle: true, format: 'iife', write: false
});
const { document, window } = parseHTML(`<html><head><title>Wrong tab title</title></head><body><main>
	<aside><h1>Wrong Recommended Job</h1>${description.repeat(5)}</aside>${selectedPanel()}
</main></body></html>`);
// A broad text selection must not override the selected LinkedIn detail panel.
window.getSelection = () => ({ toString: () => `More jobs for you ${description.repeat(4)}` });
let runtimeMessage;
vm.runInNewContext(contentBundle.outputFiles[0].text, {
	document, window, location: new URL(pageUrl), URL,
	chrome: { runtime: { sendMessage: message => { runtimeMessage = message; } } }
});
assert.equal(runtimeMessage.type, 'EXTRACTION_RESULT');
expectSelected(runtimeMessage.payload);
passed += 1;

const backgroundBundle = await build({
	entryPoints: [fileURLToPath(new URL('../../apps/extension/src/background.ts', import.meta.url))],
	bundle: true, format: 'iife', write: false
});
const listeners = [];
let capturedBody;
vm.runInNewContext(backgroundBundle.outputFiles[0].text, {
	URL, AbortSignal, setTimeout, clearTimeout, crypto: { randomUUID },
	fetch: async (url, init) => {
		assert.equal(url, 'http://127.0.0.1:8001/api/v1/jobs/capture');
		capturedBody = JSON.parse(init.body);
		return { ok: true, json: async () => ({ ref: 'SYNTHETIC', capture_completeness: 'CAPTURED_COMPLETE' }) };
	},
	chrome: {
		runtime: {
			onMessage: {
				addListener: listener => listeners.push(listener),
				removeListener: listener => listeners.splice(listeners.indexOf(listener), 1)
			},
			getManifest: () => ({ version: 'synthetic-test' })
		},
		storage: { local: { get: async () => ({ apiBaseUrl: 'http://127.0.0.1:8001/', apiKey: 'synthetic-test-only' }) } },
		tabs: { query: async () => [{ id: 7, url: pageUrl, title: 'Wrong tab title' }] },
		scripting: { executeScript: async () => {
			const extractionListener = listeners[1];
			extractionListener(runtimeMessage, { tab: { id: 7 } });
		} }
	}
});
const outcome = await new Promise(resolve => listeners[0]({ type: 'CAPTURE_ACTIVE_TAB' }, {}, resolve));
assert.equal(outcome.ok, true);
assert.equal(capturedBody.url, runtimeMessage.payload.jobUrl);
assert.equal(capturedBody.job_title, selectedTitle);
assert.equal(capturedBody.company_name, selectedCompany);
assert.equal(capturedBody.page_title, selectedTitle);
assert.equal(capturedBody.metadata.source_page_url, pageUrl);
assert.equal(normalize(capturedBody.raw_text), description);
passed += 1;

console.log(`LinkedIn capture regressions passed (${passed} synthetic DOM cases)`);
