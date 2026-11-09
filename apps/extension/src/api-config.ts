export const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

export function normalizeApiBaseUrl(value: string): string {
	let url: URL;
	try {
		url = new URL(value.trim() || DEFAULT_API_BASE_URL);
	} catch {
		throw new Error('Enter a complete API URL, for example http://127.0.0.1:8001/api/v1.');
	}
	if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
		throw new Error('Use an HTTP API URL without credentials, query parameters or fragments.');
	}
	if (['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname) && url.port === '5173') {
		throw new Error('Port 5173 is the dashboard. Use http://127.0.0.1:8001/api/v1 for the Windows API.');
	}
	let path = url.pathname.replace(/\/+$/, '');
	if (path.endsWith('/jobs/capture')) path = path.slice(0, -'/jobs/capture'.length);
	if (!path || path === '/api') path = '/api/v1';
	if (!path.endsWith('/api/v1')) {
		throw new Error('API base URL must end with /api/v1, for example http://127.0.0.1:8001/api/v1.');
	}
	return `${url.origin}${path}`;
}

export function captureHttpError(status: number, message?: unknown): string {
	if (status === 404) {
		return 'Capture endpoint not found (404). Open Settings and use http://127.0.0.1:8001/api/v1 for the Windows API, then Save.';
	}
	if (status === 401) {
		return 'API key rejected (401). In Settings, use OSCAR_API_KEY from .env.pilot and Save.';
	}
	return typeof message === 'string' && message ? message : `Save failed (${status})`;
}
