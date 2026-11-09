import { error, fail, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { ApiError, apiFetch } from '$lib/server/api';
import type {
	ApplicationOut,
	CVVersionSummary,
	GenerateCVResponse,
	JobDetail,
	JobEventOut,
	RawSnapshotOut
} from '$lib/types';

export const load: PageServerLoad = async ({ params }) => {
	let job: JobDetail;
	try {
		job = await apiFetch<JobDetail>(`/jobs/${params.id}`);
	} catch (e) {
		if (e instanceof ApiError && e.status === 404) {
			throw error(404, 'Job not found');
		}
		throw e;
	}

	let timelineUnavailable = false;
	const [raw, cvVersions, application, timeline] = await Promise.all([
		apiFetch<RawSnapshotOut>(`/jobs/${params.id}/raw`).catch(() => null),
		apiFetch<CVVersionSummary[]>(`/jobs/${params.id}/cv-versions`).catch(() => []),
		apiFetch<ApplicationOut | null>(`/jobs/${params.id}/application`).catch(() => null),
		apiFetch<JobEventOut[]>(`/jobs/${params.id}/timeline`).catch(() => {
			timelineUnavailable = true;
			return job.events;
		})
	]);
	return { job, raw, cvVersions, application, timeline, timelineUnavailable };
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
	// Both initial enrichment and later corrections append a snapshot.
	// Previously saved descriptions and CV versions are never edited here.
	enrich: async ({ request, params }) => {
		const data = await request.formData();
		const rawText = data.get('raw_text')?.toString().trim();
		if (!rawText) {
			return fail(400, { error: 'Paste the job description text.' });
		}
		try {
			await apiFetch(`/jobs/${params.id}/snapshots`, {
				method: 'POST',
				body: JSON.stringify({
					raw_text: rawText,
					capture_method: 'paste_text',
					captured_at: new Date().toISOString()
				})
			});
		} catch (e) {
			return fail(502, { error: e instanceof ApiError ? e.message : 'Enrichment failed.' });
		}
		return { success: true, descriptionSaved: true };
	},

	correct: async ({ request, params }) => {
		const data = await request.formData();
		const title = data.get('title')?.toString().trim();
		const company = data.get('company')?.toString().trim();
		try {
			await apiFetch(`/jobs/${params.id}`, {
				method: 'PATCH',
				body: JSON.stringify({
					title: title || undefined,
					company: company || undefined
				})
			});
		} catch (e) {
			return fail(502, { error: e instanceof ApiError ? e.message : 'Update failed.' });
		}
		return { success: true };
	},

	// FR-006: grounded generation. GROUNDING_FAILED/VALIDATION_FAILED/
	// LLM_REFUSED/LLM_UNAVAILABLE all surface as a plain message here rather
	// than a stack trace -- see docs/05 §1 for the error taxonomy.
	generateCv: async ({ params }) => {
		let result: GenerateCVResponse;
		try {
			result = await apiFetch<GenerateCVResponse>(`/jobs/${params.id}/generate-cv`, {
				method: 'POST',
				body: JSON.stringify({})
			});
		} catch (e) {
			if (e instanceof ApiError) {
				return fail(e.status < 500 ? 422 : 502, { error: e.message, errorType: e.errorType });
			}
			return fail(502, { error: 'CV generation failed.' });
		}
		throw redirect(303, `/cv/${result.cv_version_id}`);
	},

	// FR-008: one-click status actions. "Mark as Applied" creates the
	// Application row (linking whichever CV version was submitted, if any);
	// every later stage goes through the validated state machine (docs/04 §6)
	// via POST /applications/{id}/events, which 409s on an illegal transition.
	markApplied: async ({ request, params }) => {
		const data = await request.formData();
		const cvVersionId = data.get('cv_version_id')?.toString();
		return run(() =>
			apiFetch('/applications', {
				method: 'POST',
				body: JSON.stringify({
					job_id: Number(params.id),
					submitted_cv_version_id: cvVersionId ? Number(cvVersionId) : undefined
				})
			})
		);
	},

	addEvent: async ({ request }) => {
		const data = await request.formData();
		const applicationId = data.get('application_id');
		const eventType = data.get('event_type');
		return run(() =>
			apiFetch(`/applications/${applicationId}/events`, {
				method: 'POST',
				body: JSON.stringify({ event_type: eventType })
			})
		);
	},

	skip: async ({ params }) => run(() => apiFetch(`/jobs/${params.id}/skip`, { method: 'POST' })),
	unskip: async ({ params }) => run(() => apiFetch(`/jobs/${params.id}/unskip`, { method: 'POST' }))
};
