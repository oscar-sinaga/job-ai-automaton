// Pure configuration regressions; no browser, credentials or localhost servers.
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { build } from '../../apps/extension/node_modules/esbuild/lib/main.js';

const result = await build({
	entryPoints: [fileURLToPath(new URL('../../apps/extension/src/api-config.ts', import.meta.url))],
	bundle: true,
	format: 'esm',
	write: false
});
const config = await import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].text).toString('base64')}`);
for (const value of [
	'http://127.0.0.1:8001',
	'http://127.0.0.1:8001/',
	'http://127.0.0.1:8001/api',
	'http://127.0.0.1:8001/api/v1',
	' http://127.0.0.1:8001/api/v1/ ',
	'http://127.0.0.1:8001/api/v1/jobs/capture/'
]) {
	assert.equal(config.normalizeApiBaseUrl(value), 'http://127.0.0.1:8001/api/v1');
}
assert.equal(config.normalizeApiBaseUrl(''), 'http://127.0.0.1:8000/api/v1');
assert.equal(config.normalizeApiBaseUrl('https://example.com/oscar/api/v1/'), 'https://example.com/oscar/api/v1');
for (const value of [
	'http://127.0.0.1:5173/api/v1', 'not a URL', 'file:///tmp/config',
	'http://user:password@127.0.0.1:8001', 'http://127.0.0.1:8001/wrong',
	'http://127.0.0.1:8001/api/v1?key=secret', 'http://127.0.0.1:8001/api/v1#secret'
]) {
	assert.throws(() => config.normalizeApiBaseUrl(value));
}
assert.match(config.captureHttpError(404, 'Not Found'), /8001\/api\/v1/);
assert.match(config.captureHttpError(401), /OSCAR_API_KEY/);
assert.equal(config.captureHttpError(503, 'Backend unavailable'), 'Backend unavailable');
console.log('API URL configuration regressions passed');
