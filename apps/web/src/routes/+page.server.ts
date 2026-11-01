import type { PageServerLoad } from './$types';
import { apiFetch } from '$lib/server/api';
import type { DashboardOut } from '$lib/types';

export const load: PageServerLoad = async () => {
	const dashboard = await apiFetch<DashboardOut>('/dashboard');
	return { dashboard };
};
