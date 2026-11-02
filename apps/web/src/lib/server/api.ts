// Server-only client for the FastAPI backend. Never imported from a .svelte
// file or any code that reaches the browser -- the API key must never leave
// the server (docs/03_SYSTEM_ARCHITECTURE.md §4).
import { env } from '$env/dynamic/private';

const BASE_URL = env.API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1';
const API_KEY = env.API_KEY ?? '';

export class ApiError extends Error {
	constructor(
		public status: number,
		public errorType: string,
		message: string
	) {
		super(message);
	}
}

export async function apiRequest(path: string, init: RequestInit = {}): Promise<Response> {
	const response = await fetch(`${BASE_URL}${path}`, {
		...init,
		headers: {
			'Content-Type': 'application/json',
			'X-API-Key': API_KEY,
			...init.headers
		}
	});

	if (!response.ok) {
		const body = await response.json().catch(() => ({}));
		throw new ApiError(
			response.status,
			body.error_type ?? 'UNKNOWN',
			body.message ?? response.statusText
		);
	}
    return response;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await apiRequest(path, init);
    if (response.status === 204) return undefined as T;
	return (await response.json()) as T;
}
