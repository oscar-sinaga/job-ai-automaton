import { error, fail, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { ApiError, apiFetch } from '$lib/server/api';
import type { CVVersionOut } from '$lib/types';

export const load: PageServerLoad = async ({ params }) => {
	try {
		const cv = await apiFetch<CVVersionOut>(`/cv/${params.id}`);
		return { cv };
	} catch (e) {
		if (e instanceof ApiError && e.status === 404) {
			throw error(404, 'CV version not found');
		}
		throw e;
	}
};

async function run(fn: () => Promise<unknown>) {
	try {
		await fn();
		return { success: true };
	} catch (e) {
		return fail(e instanceof ApiError && e.status < 500 ? e.status : 502, {
			error: e instanceof ApiError ? e.message : 'Request failed.'
		});
	}
}

export const actions: Actions = {
	// Removing a bullet is a manual edit -- creates a NEW version (ADR-014);
	// the version being viewed never mutates, so this redirects to the new one.
	removeBullet: async ({ request, params }) => {
		const data = await request.formData();
		const section = data.get('section')?.toString(); // "summary" | "experience" | "projects"
		const blockIndex = Number(data.get('blockIndex') ?? -1);
		const bulletIndex = Number(data.get('bulletIndex') ?? -1);

		const cv = await apiFetch<CVVersionOut>(`/cv/${params.id}`);
		const sections = structuredClone(cv.sections);

		if (section === 'summary') {
			sections.summary = { text: '', supporting_fact_ids: [] };
		} else if ((section === 'experience' || section === 'projects') && blockIndex >= 0) {
			sections[section][blockIndex].bullets.splice(bulletIndex, 1);
		}

		let updated: CVVersionOut;
		try {
			updated = await apiFetch<CVVersionOut>(`/cv/${params.id}`, {
				method: 'PATCH',
				body: JSON.stringify({ sections })
			});
		} catch (e) {
			return fail(e instanceof ApiError && e.status < 500 ? e.status : 502, {
				error: e instanceof ApiError ? e.message : 'Edit failed.'
			});
		}
		throw redirect(303, `/cv/${updated.id}`);
	},

	approve: async ({ params }) => run(() => apiFetch(`/cv/${params.id}/approve`, { method: 'POST' })),
	export: async ({ params }) => run(() => apiFetch(`/cv/${params.id}/export`, { method: 'POST' })),
	markSubmitted: async ({ params }) =>
		run(() => apiFetch(`/cv/${params.id}/mark-submitted`, { method: 'POST' }))
};
