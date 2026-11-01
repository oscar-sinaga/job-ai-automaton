import type { PageServerLoad } from './$types';
import { apiFetch } from '$lib/server/api';
import type { ProductivityOut, SourceOrRoleStat, TrendPoint } from '$lib/types';

export const load: PageServerLoad = async ({ url }) => {
	const granularity = url.searchParams.get('granularity') === 'month' ? 'month' : 'week';

	const [trends, sources, roles, productivity] = await Promise.all([
		apiFetch<TrendPoint[]>(`/analytics/trends?granularity=${granularity}`),
		apiFetch<SourceOrRoleStat[]>('/analytics/sources'),
		apiFetch<SourceOrRoleStat[]>('/analytics/roles'),
		apiFetch<ProductivityOut>('/analytics/productivity')
	]);

	return { trends, sources, roles, productivity, granularity };
};
