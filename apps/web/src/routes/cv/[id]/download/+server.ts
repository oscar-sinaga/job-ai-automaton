import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { ApiError, apiRequest } from '$lib/server/api';

export const GET: RequestHandler = async ({ params, url }) => {
	const artifactId = url.searchParams.get('artifact');
	if (!/^\d+$/.test(params.id) || !artifactId || !/^\d+$/.test(artifactId)) {
		error(400, 'Choose a valid CV and PDF artifact.');
	}
	try {
		const response = await apiRequest(`/cv/${params.id}/artifacts/${artifactId}/download`);
		return new Response(response.body, {
			headers: {
				'Content-Type': 'application/pdf',
				'Content-Disposition': response.headers.get('Content-Disposition') ?? 'attachment; filename="CV.pdf"',
				'Cache-Control': 'private, no-store',
				'X-Content-Type-Options': 'nosniff'
			}
		});
	} catch (e) {
		if (e instanceof ApiError) error(e.status, e.message);
		error(502, 'Could not download the saved PDF. Try exporting it again.');
	}
};
