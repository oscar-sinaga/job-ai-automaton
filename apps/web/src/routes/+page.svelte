<script lang="ts">
	import { appPath } from '$lib/app-path';

	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	function pct(value: number | null): string {
		return value === null ? '—' : `${Math.round(value * 100)}%`;
	}

	const kpiCards = $derived([
		{ label: 'Saved', value: data.dashboard.kpis.saved },
		{ label: 'Ready to Apply', value: data.dashboard.kpis.ready_to_apply },
		{ label: 'Applied', value: data.dashboard.kpis.applied },
		{ label: 'Assessment', value: data.dashboard.kpis.assessment },
		{ label: 'Interview', value: data.dashboard.kpis.interview },
		{ label: 'Final Interview', value: data.dashboard.kpis.final_interview },
		{ label: 'Offer', value: data.dashboard.kpis.offer },
		{ label: 'Rejected', value: data.dashboard.kpis.rejected }
	]);

	const maxFunnelCount = $derived(Math.max(1, ...data.dashboard.funnel.map((f) => f.count)));
</script>

<div class="max-w-4xl space-y-8">
	<div>
		<h1 class="text-xl font-semibold text-slate-900">Dashboard</h1>
		<p class="mt-1 text-xs text-slate-500">{data.dashboard.sample_note}</p>
	</div>

	<!-- Action queue: dashboard should not be passive (FR-011) -->
	{#if data.dashboard.action_queue.length}
		<section class="rounded border border-amber-200 bg-amber-50 p-4">
			<h2 class="text-sm font-semibold text-amber-900">Action queue</h2>
			<ul class="mt-2 space-y-1">
				{#each data.dashboard.action_queue as item (item.label)}
					<li class="text-sm">
						<a href={appPath(item.href)} class="text-amber-900 underline underline-offset-2">
							{item.count} {item.label}
						</a>
					</li>
				{/each}
			</ul>
		</section>
	{/if}

	<!-- KPIs -->
	<section class="grid grid-cols-2 gap-3 sm:grid-cols-4">
		{#each kpiCards as card (card.label)}
			<div class="rounded border border-slate-200 bg-white p-3">
				<p class="text-2xl font-semibold text-slate-900">{card.value}</p>
				<p class="text-xs text-slate-500">{card.label}</p>
			</div>
		{/each}
	</section>

	<!-- Funnel -->
	<section class="rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Funnel</h2>
		<p class="mt-1 text-xs text-slate-500">
			Stages aren't strictly nested — assessment is optional, so interview can exceed assessment.
		</p>
		<div class="mt-3 space-y-2">
			{#each data.dashboard.funnel as stage (stage.stage)}
				<div class="flex items-center gap-2 text-sm">
					<span class="w-32 shrink-0 text-slate-600">{stage.stage}</span>
					<div class="h-4 flex-1 rounded bg-slate-100">
						<div
							class="h-4 rounded bg-slate-900"
							style="width: {(stage.count / maxFunnelCount) * 100}%"
						></div>
					</div>
					<span class="w-8 shrink-0 text-right text-slate-700">{stage.count}</span>
				</div>
			{/each}
		</div>
	</section>

	<!-- Conversion -->
	<section class="rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Conversion</h2>
		<div class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
			<div>
				<p class="text-lg font-semibold">{pct(data.dashboard.conversion.applied_over_saved)}</p>
				<p class="text-xs text-slate-500">Applied / Saved</p>
			</div>
			<div>
				<p class="text-lg font-semibold">
					{pct(data.dashboard.conversion.assessment_over_applied)}
				</p>
				<p class="text-xs text-slate-500">Assessment / Applied</p>
			</div>
			<div>
				<p class="text-lg font-semibold">
					{pct(data.dashboard.conversion.interview_over_applied)}
				</p>
				<p class="text-xs text-slate-500">Interview / Applied</p>
			</div>
			<div>
				<p class="text-lg font-semibold">{pct(data.dashboard.conversion.offer_over_interview)}</p>
				<p class="text-xs text-slate-500">Offer / Interview</p>
			</div>
			<div>
				<p class="text-lg font-semibold">{pct(data.dashboard.conversion.offer_over_applied)}</p>
				<p class="text-xs text-slate-500">Offer / Applied</p>
			</div>
		</div>
	</section>

	<!-- Backlog -->
	<section class="rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Backlog</h2>
		<div class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
			<div>
				<p class="text-lg font-semibold">{data.dashboard.backlog.cv_ready_not_applied}</p>
				<p class="text-xs text-slate-500">CV ready, not applied</p>
			</div>
			<div>
				<p class="text-lg font-semibold">{data.dashboard.backlog.saved_older_than_5d}</p>
				<p class="text-xs text-slate-500">Saved &gt; 5 days</p>
			</div>
			<div>
				<p class="text-lg font-semibold">{data.dashboard.backlog.jobs_without_cv}</p>
				<p class="text-xs text-slate-500">Missing a CV</p>
			</div>
			<div>
				<p class="text-lg font-semibold">{data.dashboard.backlog.applications_needing_action}</p>
				<p class="text-xs text-slate-500">Needing follow-up</p>
			</div>
			<div>
				<p class="text-lg font-semibold">{data.dashboard.backlog.partial_captures}</p>
				<p class="text-xs text-slate-500">Partial captures</p>
			</div>
		</div>
	</section>

	<a href={appPath(`/analytics`)} class="inline-block text-sm text-slate-600 underline underline-offset-2">
		Full analytics: trends, sources, roles →
	</a>
</div>
