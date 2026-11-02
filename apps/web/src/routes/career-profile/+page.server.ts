import { fail } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { ApiError, apiFetch } from '$lib/server/api';
import type { CareerProfile } from '$lib/types';

export const load: PageServerLoad = async () => {
	const profile = await apiFetch<CareerProfile>('/career-profile');
	return { profile };
};

function str(form: FormData, key: string): string | undefined {
	const value = form.get(key)?.toString().trim();
	return value || undefined;
}

function num(form: FormData, key: string): number | undefined {
	const value = str(form, key);
	return value ? Number(value) : undefined;
}

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
	updateSummary: async ({ request }) => {
		const form = await request.formData();
		return run(() =>
			apiFetch('/career-profile', {
				method: 'PATCH',
				body: JSON.stringify({ summary: str(form, 'summary') ?? '' })
			})
		);
	},

	addExperience: async ({ request }) => {
		const form = await request.formData();
		return run(() =>
			apiFetch('/career-profile/experiences', {
				method: 'POST',
				body: JSON.stringify({
					company: str(form, 'company'),
					title: str(form, 'title'),
					location: str(form, 'location'),
					start_date: str(form, 'start_date'),
					end_date: str(form, 'end_date'),
					is_current: form.get('is_current') === 'on',
					description: str(form, 'description')
				})
			})
		);
	},
	deleteExperience: async ({ request }) => {
		const form = await request.formData();
		return run(() => apiFetch(`/career-profile/experiences/${form.get('id')}`, { method: 'DELETE' }));
	},

	addProject: async ({ request }) => {
		const form = await request.formData();
		return run(() =>
			apiFetch('/career-profile/projects', {
				method: 'POST',
				body: JSON.stringify({
					name: str(form, 'name'),
					description: str(form, 'description'),
					link: str(form, 'link')
				})
			})
		);
	},
	deleteProject: async ({ request }) => {
		const form = await request.formData();
		return run(() => apiFetch(`/career-profile/projects/${form.get('id')}`, { method: 'DELETE' }));
	},

	// The fact store CV grounding will cite in M3 -- see docs/07 §2.
	addAchievement: async ({ request }) => {
		const form = await request.formData();
		const tags = (key: string) =>
			(str(form, key) ?? '')
				.split(',')
				.map((t) => t.trim())
				.filter(Boolean);
		return run(() =>
			apiFetch('/career-profile/achievements', {
				method: 'POST',
				body: JSON.stringify({
					statement: str(form, 'statement'),
					experience_id: num(form, 'experience_id'),
					project_id: num(form, 'project_id'),
					metric_value: str(form, 'metric_value'),
					metric_verified: form.get('metric_verified') === 'on',
					skill_tags: tags('skill_tags'),
					domain_tags: tags('domain_tags'),
					technology_tags: tags('technology_tags')
				})
			})
		);
	},
	deleteAchievement: async ({ request }) => {
		const form = await request.formData();
		return run(() =>
			apiFetch(`/career-profile/achievements/${form.get('id')}`, { method: 'DELETE' })
		);
	},

	addSkill: async ({ request }) => {
		const form = await request.formData();
		return run(() =>
			apiFetch('/career-profile/skills', {
				method: 'POST',
				body: JSON.stringify({
					name: str(form, 'name'),
					category: str(form, 'category'),
					years_experience: num(form, 'years_experience')
				})
			})
		);
	},
	deleteSkill: async ({ request }) => {
		const form = await request.formData();
		return run(() => apiFetch(`/career-profile/skills/${form.get('id')}`, { method: 'DELETE' }));
	},

	addEducation: async ({ request }) => {
		const form = await request.formData();
		return run(() =>
			apiFetch('/career-profile/education', {
				method: 'POST',
				body: JSON.stringify({
					institution: str(form, 'institution'),
					degree: str(form, 'degree'),
					field: str(form, 'field')
				})
			})
		);
	},
	deleteEducation: async ({ request }) => {
		const form = await request.formData();
		return run(() => apiFetch(`/career-profile/education/${form.get('id')}`, { method: 'DELETE' }));
	},

	addCertification: async ({ request }) => {
		const form = await request.formData();
		return run(() =>
			apiFetch('/career-profile/certifications', {
				method: 'POST',
				body: JSON.stringify({
					name: str(form, 'name'),
					issuer: str(form, 'issuer')
				})
			})
		);
	},
	deleteCertification: async ({ request }) => {
		const form = await request.formData();
		return run(() =>
			apiFetch(`/career-profile/certifications/${form.get('id')}`, { method: 'DELETE' })
		);
	},

	updateApplicationProfile: async ({ request }) => {
		const form = await request.formData();
		const current = await apiFetch<CareerProfile>('/career-profile');
		const links = { ...current.application_profile.links };
		for (const key of ['name', 'email', 'phone', 'linkedin', 'github', 'portfolio']) {
			links[`cv_${key}`] = str(form, `cv_${key}`) ?? '';
		}
		return run(() =>
			apiFetch('/career-profile/application-profile', {
				method: 'PATCH',
				body: JSON.stringify({
					links,
					notice_period: str(form, 'notice_period'),
					salary_expectation: str(form, 'salary_expectation'),
					work_authorization: str(form, 'work_authorization'),
					relocation_ok: form.has('relocation_ok_present')
						? form.get('relocation_ok') === 'on'
						: undefined,
					preferred_location: str(form, 'preferred_location')
				})
			})
		);
	}
};
