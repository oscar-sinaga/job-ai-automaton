import { fail } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { ApiError, apiFetch } from '$lib/server/api';
import type { JobList } from '$lib/types';

const FILTER_KEYS = ['status', 'source', 'q', 'cursor'] as const;

export const load: PageServerLoad = async ({ url }) => {
	const params = new URLSearchParams();
	for (const key of FILTER_KEYS) {
		const value = url.searchParams.get(key);
		if (value) params.set(key, value);
	}

	const query = params.toString();
	const jobs = await apiFetch<JobList>(`/jobs${query ? `?${query}` : ''}`);
	return {
		jobs,
		status: url.searchParams.get('status') ?? '',
		source: url.searchParams.get('source') ?? '',
		q: url.searchParams.get('q') ?? ''
	};
};

export const actions: Actions = {
	// The manual-URL and paste-text fallbacks (docs/08 §7) -- V1 is fully usable
	// without the browser extension.
	capture: async ({ request }) => {
		const data = await request.formData();
		const url = data.get('url')?.toString().trim();
		const rawText = data.get('raw_text')?.toString().trim();

		if (!url) {
			return fail(400, { error: 'A job URL is required.' });
		}

		try {
			await apiFetch('/jobs/capture', {
				method: 'POST',
				body: JSON.stringify({
					url,
					raw_text: rawText || undefined,
					captured_at: new Date().toISOString(),
					capture_method: rawText ? 'paste_text' : 'manual_url'
				})
			});
		} catch (e) {
			const message = e instanceof ApiError ? e.message : 'Capture failed.';
			return fail(502, { error: message });
		}

		return { success: true };
	}
};
