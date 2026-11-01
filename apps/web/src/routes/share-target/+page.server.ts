import type { PageServerLoad } from './$types';
import { ApiError, apiFetch } from '$lib/server/api';
import type { CaptureResponse } from '$lib/types';

// PWA Web Share Target (ADR-020, docs/09 §3): the OS share sheet navigates
// here with a GET request, so this load function *is* the capture action --
// there is no separate form step. The share payload is frequently URL/title
// only, with no JD text, which is exactly the CAPTURED_PARTIAL case the
// server derives on its own (ADR-012); this route never pretends otherwise.
export const load: PageServerLoad = async ({ url }) => {
	const sharedUrl = url.searchParams.get('url')?.trim();
	const title = url.searchParams.get('title')?.trim();
	const text = url.searchParams.get('text')?.trim();

	// Some share sources put the link inside `text` instead of `url`.
	const resolvedUrl = sharedUrl || extractUrl(text) || '';

	if (!resolvedUrl) {
		return {
			outcome: 'error' as const,
			message: 'No URL was found in the shared content.'
		};
	}

	try {
		const capture = await apiFetch<CaptureResponse>('/jobs/capture', {
			method: 'POST',
			body: JSON.stringify({
				url: resolvedUrl,
				page_title: title || undefined,
				shared_text: text || undefined,
				capture_method: 'mobile_share',
				captured_at: new Date().toISOString()
			})
		});
		return { outcome: 'success' as const, capture };
	} catch (e) {
		return {
			outcome: 'error' as const,
			message: e instanceof ApiError ? e.message : 'Save failed.'
		};
	}
};

function extractUrl(text: string | null | undefined): string | null {
	if (!text) return null;
	const match = text.match(/https?:\/\/\S+/);
	return match ? match[0] : null;
}
