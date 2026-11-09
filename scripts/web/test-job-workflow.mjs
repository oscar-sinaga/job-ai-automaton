// Run after `npm run build` in apps/web. Exercises the production Node server
// with an in-memory loopback API: no browser, database, provider or env file.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../..', import.meta.url));
const webRoot = path.join(root, 'apps/web');
const entry = path.join(webRoot, 'build/index.js');
assert(fs.existsSync(entry), 'Build apps/web before running the workflow regressions');
const key = 'synthetic-web-workflow-only';
const calls = [];
const original = 'Original synthetic description with unrelated recommendations that needs correction.';
const corrected = 'Corrected fictional Data Engineer description. Build Python pipelines, document transformations and maintain data quality.';
const savedAt = '2026-01-01T10:00:00Z';
const jobEvents = [
	{ event_type: 'JOB_SAVED', actor: 'user', metadata: {}, occurred_at: savedAt },
	{ event_type: 'CV_GENERATED', actor: 'system', metadata: { cv_version_id: 101 }, occurred_at: '2026-01-01T11:00:00Z' }
];
const timeline = [
	...jobEvents,
	{ event_type: 'APPLICATION_SUBMITTED', actor: 'user', metadata: { attempt: 1 }, occurred_at: '2026-01-02T10:00:00Z' },
	{ event_type: 'INTERVIEW_RECEIVED', actor: 'user', metadata: { round: 1 }, occurred_at: '2026-01-03T10:00:00Z' },
	{ event_type: 'APPLICATION_SUBMITTED', actor: 'user', metadata: { attempt: 2 }, occurred_at: '2026-02-02T10:00:00Z' },
	{ event_type: 'INTERVIEW_RECEIVED', actor: 'user', metadata: { round: 2 }, occurred_at: '2026-02-03T10:00:00Z' }
];
const snapshots = [{ id: 1, raw_text: original, capture_method: 'extension', captured_at: savedAt }];
let timelineFailure = false;
let child;
let serverOutput = '';
let passed = 0;

function summary(id = 1) {
	return { id, ref: `J00${id}`, title: 'Synthetic Data Engineer', company: 'Example Employer', source: 'example.test',
		current_status: id === 1 ? 'INTERVIEW' : 'SAVED', capture_completeness: id === 1 ? 'CAPTURED_COMPLETE' : 'NEEDS_ENRICHMENT',
		cv_ready: id === 1, latest_cv_version: id === 1 ? 1 : null, created_at: savedAt, is_duplicate: false };
}
function detail(id) {
	return { ...summary(id), url: `https://example.test/job/${id}`, canonical_url: `https://example.test/job/${id}`,
		duplicate_of_job_id: null, updated_at: savedAt, events: id === 1 ? jobEvents : [jobEvents[0]],
		snapshots: id === 1 ? snapshots.map(snapshot => ({ ...snapshot, raw_text: undefined, raw_text_length: snapshot.raw_text.length, page_title: null })) : [] };
}
function json(response, value, status = 200) {
	response.writeHead(status, { 'Content-Type': 'application/json' });
	response.end(JSON.stringify(value));
}
const api = http.createServer(async (request, response) => {
	try {
		assert.equal(request.headers['x-api-key'], key, 'Only the synthetic key may reach the fixture API');
		const url = new URL(request.url, 'http://fixture.test');
		calls.push({ method: request.method, path: url.pathname, query: url.searchParams });
		if (request.method === 'GET' && url.pathname === '/api/v1/jobs') return json(response, { items: [summary()], next_cursor: 'next+cursor/=' });
		const match = url.pathname.match(/^\/api\/v1\/jobs\/([12])(?:\/(raw|cv-versions|application|timeline|snapshots))?$/);
		if (!match) return json(response, { message: 'Unexpected synthetic API route' }, 404);
		const id = Number(match[1]);
		const route = match[2];
		if (request.method === 'POST' && route === 'snapshots') {
			let body = '';
			for await (const chunk of request) body += chunk;
			const payload = JSON.parse(body);
			calls.at(-1).body = payload;
			assert.equal(payload.capture_method, 'paste_text');
			assert.equal(typeof payload.captured_at, 'string');
			snapshots.push({ id: snapshots.length + 1, ...payload });
			return json(response, { snapshot_id: snapshots.length, capture_completeness: 'CAPTURED_COMPLETE' }, 201);
		}
		if (request.method !== 'GET') return json(response, { message: 'Unexpected synthetic mutation' }, 405);
		if (!route) return json(response, detail(id));
		if (route === 'raw') return json(response, id === 1 ? { snapshot_id: snapshots.at(-1).id, raw_text: snapshots.at(-1).raw_text } : { snapshot_id: 20, raw_text: null });
		if (route === 'cv-versions') return json(response, id === 1 ? [{ id: 101, version_number: 1, is_submitted: true, created_at: savedAt }] : []);
		if (route === 'application') return json(response, id === 1 ? { id: 12, job_id: 1, submitted_cv_version_id: 101, current_status: 'INTERVIEW', created_at: savedAt } : null);
		if (route === 'timeline') return timelineFailure ? json(response, { message: 'Synthetic history unavailable' }, 503) : json(response, id === 1 ? timeline : [jobEvents[0]]);
		return json(response, { message: 'Unexpected synthetic request' }, 404);
	} catch (error) { json(response, { message: error.message }, 500); }
});
async function listen(server) {
	await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
	return server.address().port;
}
function decode(value) {
	return value.replaceAll('&amp;', '&').replaceAll('&quot;', '"').replaceAll('&#39;', "'").replaceAll('&lt;', '<').replaceAll('&gt;', '>');
}
function attribute(tag, name) {
	const match = tag.match(new RegExp(`\\b${name}=(?:"([^"]*)"|'([^']*)'|([^\\s>]+))`));
	return match ? decode(match[1] ?? match[2] ?? match[3]) : null;
}
function timelineHtml(html) {
	const heading = /<h2\b[^>]*>Timeline<\/h2>/.exec(html);
	assert(heading, 'Timeline heading is present');
	return html.slice(heading.index).match(/<ol\b[^>]*>([\s\S]*?)<\/ol>/)[1];
}
async function html(url, init) {
	const response = await fetch(url, init);
	assert.equal(response.status, 200, `Unexpected response for ${url}`);
	const result = await response.text();
	assert(!result.includes(key), 'The server key must never enter rendered HTML');
	return result;
}
function lastListCall() { return calls.filter(call => call.path === '/api/v1/jobs').at(-1); }

try {
	const apiPort = await listen(api);
	const reservation = http.createServer();
	const webPort = await listen(reservation);
	await new Promise(resolve => reservation.close(resolve));
	const origin = `http://127.0.0.1:${webPort}`;
	const inherited = Object.fromEntries(['PATH', 'SystemRoot', 'TEMP', 'TMP'].filter(name => process.env[name]).map(name => [name, process.env[name]]));
	child = spawn(process.execPath, [entry], { cwd: webRoot, windowsHide: true, env: {
		...inherited, HOST: '127.0.0.1', PORT: String(webPort), ORIGIN: origin,
		API_BASE_URL: `http://127.0.0.1:${apiPort}/api/v1`, API_KEY: key, NODE_ENV: 'production'
	}, stdio: ['ignore', 'pipe', 'pipe'] });
	for (const stream of [child.stdout, child.stderr]) stream.on('data', value => { serverOutput = (serverOutput + value).slice(-8000); });
	child.on('error', error => { serverOutput += error.message; });
	let ready = false;
	for (let attempt = 0; attempt < 100; attempt++) {
		if (child.exitCode !== null) throw new Error(`Production server exited: ${serverOutput}`);
		try { ready = (await fetch(`${origin}/jobs`)).ok; } catch { /* waiting for the owned server */ }
		if (ready) break;
		await new Promise(resolve => setTimeout(resolve, 50));
	}
	assert(ready, `Production server did not become ready: ${serverOutput}`);
	for (const query of ['missing_cv=1', 'needs_action=1', 'completeness=CAPTURED_PARTIAL', 'status=SAVED&older_than=5d', 'needs_description=1&exclude_duplicates=1']) {
		const page = await html(`${origin}/jobs?${query}`);
		assert.deepEqual([...lastListCall().query], [...new URLSearchParams(query)]);
		if (query.includes('needs_description')) {
			assert(page.includes('Needs full description') && page.includes('Duplicates excluded'));
			assert(!page.includes('Needs follow-up'), 'Description/duplicate filters must have accurate labels');
		}
		passed++;
	}
	const filters = new URLSearchParams({ status: 'INTERVIEW', source: 'linkedin.com', q: 'Data & ML', completeness: 'CAPTURED_COMPLETE', older_than: '5d', missing_cv: 'true', needs_action: '1', needs_description: '1', exclude_duplicates: '1', limit: '2' });
	const inbox = await html(`${origin}/jobs?${filters}`);
	const nextAnchor = [...inbox.matchAll(/<a\b[^>]*>[\s\S]*?<\/a>/g)].map(match => match[0]).find(anchor => anchor.includes('Next page'));
	const next = new URL(attribute(nextAnchor, 'href'), `${origin}/jobs`);
	for (const [name, value] of filters) assert.equal(next.searchParams.get(name), value);
	assert.equal(next.searchParams.get('cursor'), 'next+cursor/=');
	await html(next);
	assert.deepEqual([...lastListCall().query].sort(), [...next.searchParams].sort());
	passed++;
	const filterForm = [...(await html(next)).matchAll(/<form\b[^>]*>[\s\S]*?<\/form>/g)].map(match => match[0]).find(form => attribute(form, 'method') === 'get');
	const formValues = new URLSearchParams();
	for (const input of filterForm.matchAll(/<input\b[^>]*>/g)) if (attribute(input[0], 'type') === 'hidden') formValues.set(attribute(input[0], 'name'), attribute(input[0], 'value'));
	for (const name of ['completeness', 'older_than', 'missing_cv', 'needs_action', 'needs_description', 'exclude_duplicates', 'limit']) assert.equal(formValues.get(name), filters.get(name));
	assert(!formValues.has('cursor'), 'Changing filters starts at the first page');
	formValues.set('status', 'SAVED');
	await html(`${origin}/jobs?${formValues}`);
	assert.deepEqual([...lastListCall().query].sort(), [...formValues].sort());
	passed++;
	calls.length = 0;
	const completeJob = await html(`${origin}/jobs/1`);
	assert(completeJob.includes('Correct job description') && completeJob.includes('Save corrected description'));
	assert(completeJob.includes('Earlier descriptions and'));
	assert.match(completeJob, /action="\?\/enrich"/);
	const renderedTimeline = timelineHtml(completeJob);
	assert.equal((renderedTimeline.match(/APPLICATION_SUBMITTED/g) ?? []).length, 2);
	assert.equal((renderedTimeline.match(/INTERVIEW_RECEIVED/g) ?? []).length, 2);
	assert.equal((renderedTimeline.match(/JOB_SAVED/g) ?? []).length, 1);
	assert.deepEqual(renderedTimeline.match(/JOB_SAVED|CV_GENERATED|APPLICATION_SUBMITTED|INTERVIEW_RECEIVED/g), timeline.map(event => event.event_type));
	assert(renderedTimeline.includes('system') && renderedTimeline.includes('user'));
	assert(decode(renderedTimeline).includes('"round": 2'));
	assert.equal(calls.filter(call => call.path.endsWith('/timeline')).length, 1);
	assert(!calls.some(call => call.path.startsWith('/api/v1/applications/')), 'The unified timeline must not trigger per-application fetches');
	passed++;
	const before = snapshots[0].raw_text;
	const correctedPage = await html(`${origin}/jobs/1?/enrich`, { method: 'POST', headers: { Origin: origin, Accept: 'text/html' }, body: new URLSearchParams({ raw_text: corrected }) });
	assert.equal(snapshots.length, 2);
	assert.equal(snapshots[0].raw_text, before);
	assert.equal(calls.filter(call => call.method === 'POST').at(-1).path, '/api/v1/jobs/1/snapshots');
	assert(correctedPage.includes(corrected) && correctedPage.includes('Description saved as a new snapshot.'));
	assert(!calls.some(call => ['PATCH', 'DELETE'].includes(call.method)), 'Correction appends, never rewrites earlier records');
	passed++;
	const mutations = calls.filter(call => call.method === 'POST').length;
	const invalid = await fetch(`${origin}/jobs/1?/enrich`, { method: 'POST', headers: { Origin: origin, Accept: 'text/html' }, body: new URLSearchParams({ raw_text: '   ' }) });
	assert.equal(invalid.status, 400);
	assert.equal(calls.filter(call => call.method === 'POST').length, mutations);
	passed++;
	calls.length = 0;
	const partialJob = await html(`${origin}/jobs/2`);
	assert(partialJob.includes('Job description not saved yet') && partialJob.includes('Save description'));
	assert(!calls.some(call => call.path.startsWith('/api/v1/applications/')));
	assert.equal((timelineHtml(partialJob).match(/JOB_SAVED/g) ?? []).length, 1);
	passed++;
	timelineFailure = true;
	const fallback = await html(`${origin}/jobs/1`);
	assert(fallback.includes('Application history could not be loaded.'));
	assert.equal((timelineHtml(fallback).match(/JOB_SAVED/g) ?? []).length, 1);
	assert(!timelineHtml(fallback).includes('APPLICATION_SUBMITTED'));
	passed++;
	console.log(`Web job workflow regressions passed (${passed} production-server HTTP cases)`);
} catch (error) {
	if (serverOutput) console.error(serverOutput);
	throw error;
} finally {
	if (child?.pid && child.exitCode === null) { const exited = once(child, 'exit'); child.kill(); await exited; }
	api.closeAllConnections();
	await new Promise(resolve => api.close(resolve));
}
