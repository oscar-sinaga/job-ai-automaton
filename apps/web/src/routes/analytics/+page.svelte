<script lang="ts">
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	function pct(value: number | null): string {
		return value === null ? '—' : `${Math.round(value * 100)}%`;
	}

	function days(value: number | null): string {
		return value === null ? '—' : `${value.toFixed(1)}d`;
	}

	const maxTrend = $derived(Math.max(1, ...data.trends.map((t) => t.saved)));
</script>

<div class="max-w-4xl space-y-8">
	<div>
		<h1 class="text-xl font-semibold text-slate-900">Analytics</h1>
		<p class="mt-1 text-xs text-slate-500">
			Describes your captured-job sample, not the job market.
		</p>
	</div>

	<!-- Productivity -->
	<section class="rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Productivity</h2>
		<div class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
			<div>
				<p class="text-lg font-semibold">{days(data.productivity.median_saved_to_cv_ready_days)}</p>
				<p class="text-xs text-slate-500">Median saved → CV ready</p>
			</div>
			<div>
				<p class="text-lg font-semibold">{days(data.productivity.median_saved_to_applied_days)}</p>
				<p class="text-xs text-slate-500">Median saved → applied</p>
			</div>
			<div>
				<p class="text-lg font-semibold">{data.productivity.applications_last_7d}</p>
				<p class="text-xs text-slate-500">Applications, last 7 days</p>
			</div>
			<div>
				<p class="text-lg font-semibold">{data.productivity.backlog_size}</p>
				<p class="text-xs text-slate-500">Backlog size</p>
			</div>
		</div>
	</section>

	<!-- Trends -->
	<section class="rounded border border-slate-200 bg-white p-4">
		<div class="flex items-center justify-between">
			<h2 class="text-sm font-semibold text-slate-900">Trends</h2>
			<div class="flex gap-2 text-xs">
				<a
					href="?granularity=week"
					class="rounded px-2 py-1 {data.granularity === 'week'
						? 'bg-slate-900 text-white'
						: 'text-slate-600 hover:bg-slate-100'}">Week</a
				>
				<a
					href="?granularity=month"
					class="rounded px-2 py-1 {data.granularity === 'month'
						? 'bg-slate-900 text-white'
						: 'text-slate-600 hover:bg-slate-100'}">Month</a
				>
			</div>
		</div>
		{#if data.trends.length}
			<div class="mt-3 flex items-end gap-1" style="height: 120px">
				{#each data.trends as point (point.bucket)}
					<div class="flex flex-1 flex-col items-center justify-end gap-1" title={point.bucket}>
						<div
							class="w-full rounded-t bg-slate-900"
							style="height: {(point.saved / maxTrend) * 100}%"
						></div>
						<span class="text-[10px] text-slate-400"
							>{new Date(point.bucket).toLocaleDateString(undefined, {
								month: 'short',
								day: 'numeric'
							})}</span
						>
					</div>
				{/each}
			</div>
			<p class="mt-2 text-xs text-slate-500">Bars show jobs saved per bucket.</p>
		{:else}
			<p class="mt-2 text-sm text-slate-500">No data yet.</p>
		{/if}
	</section>

	<!-- Sources -->
	<section class="rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">By source</h2>
		<table class="mt-3 w-full text-left text-sm">
			<thead class="text-xs uppercase text-slate-500">
				<tr><th class="py-1">Source</th><th>Saved</th><th>Applied</th><th>Interview</th><th
						>Applied rate</th
					></tr
				>
			</thead>
			<tbody>
				{#each data.sources as s (s.name)}
					<tr class="border-t border-slate-100">
						<td class="py-1">{s.name}</td>
						<td>{s.saved}</td>
						<td>{s.applied}</td>
						<td>{s.interview}</td>
						<td>{pct(s.applied_rate)}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</section>

	<!-- Roles -->
	<section class="rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">By role</h2>
		<table class="mt-3 w-full text-left text-sm">
			<thead class="text-xs uppercase text-slate-500">
				<tr><th class="py-1">Role</th><th>Saved</th><th>Applied</th><th>Interview</th><th
						>Applied rate</th
					></tr
				>
			</thead>
			<tbody>
				{#each data.roles as r (r.name)}
					<tr class="border-t border-slate-100">
						<td class="py-1">{r.name}</td>
						<td>{r.saved}</td>
						<td>{r.applied}</td>
						<td>{r.interview}</td>
						<td>{pct(r.applied_rate)}</td>
					</tr>
				{/each}
			</tbody>
		</table>
		<p class="mt-2 text-xs text-slate-500">
			Role classification isn't built yet (needs the job parser, P1) — everything shows as
			"unclassified" for now.
		</p>
	</section>

	<!-- Skills (not built) -->
	<section class="rounded border border-slate-200 bg-slate-50 p-4">
		<h2 class="text-sm font-semibold text-slate-900">Skills</h2>
		<p class="mt-1 text-sm text-slate-600">
			Not available yet — requires job_skills data from the job_parser agent (P1, not yet built).
		</p>
	</section>
</div>
