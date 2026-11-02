<script lang="ts">
	import { enhance } from '$app/forms';
	import type { PageProps } from './$types';

	let { data, form }: PageProps = $props();

	const needsEnrichment = $derived(
		data.job.capture_completeness === 'NEEDS_ENRICHMENT' ||
			data.job.capture_completeness === 'CAPTURED_PARTIAL'
	);

	// Mirrors the backend state machine (docs/04 §6) for UX only -- the
	// server (modules/applications/state_machine.py) is the actual authority
	// and will 409 on anything illegal regardless of what this shows.
	const NEXT_STEP_BUTTONS: Record<string, { label: string; eventType: string }[]> = {
		APPLIED: [
			{ label: 'Assessment received', eventType: 'ASSESSMENT_RECEIVED' },
			{ label: 'Interview received', eventType: 'INTERVIEW_RECEIVED' },
			{ label: 'Rejected', eventType: 'REJECTED' },
			{ label: 'Offer received', eventType: 'OFFER_RECEIVED' },
			{ label: 'Withdraw', eventType: 'WITHDRAWN' }
		],
		ASSESSMENT: [
			{ label: 'Interview received', eventType: 'INTERVIEW_RECEIVED' },
			{ label: 'Rejected', eventType: 'REJECTED' },
			{ label: 'Withdraw', eventType: 'WITHDRAWN' }
		],
		INTERVIEW: [
			{ label: 'Another interview round', eventType: 'INTERVIEW_RECEIVED' },
			{ label: 'Final interview', eventType: 'FINAL_INTERVIEW' },
			{ label: 'Offer received', eventType: 'OFFER_RECEIVED' },
			{ label: 'Rejected', eventType: 'REJECTED' },
			{ label: 'Withdraw', eventType: 'WITHDRAWN' }
		],
		FINAL_INTERVIEW: [
			{ label: 'Offer received', eventType: 'OFFER_RECEIVED' },
			{ label: 'Rejected', eventType: 'REJECTED' },
			{ label: 'Withdraw', eventType: 'WITHDRAWN' }
		],
		OFFER: [{ label: 'Withdraw', eventType: 'WITHDRAWN' }]
	};

	const canSkip = $derived(
		['SAVED', 'READY_TO_APPLY', 'APPLYING'].includes(data.job.current_status)
	);
	const nextSteps = $derived(NEXT_STEP_BUTTONS[data.job.current_status] ?? []);
</script>

<div class="max-w-3xl">
	<a href="/jobs" class="text-sm text-slate-500 underline underline-offset-2">← Job Inbox</a>

	<div class="mt-2 flex items-center gap-3">
		<h1 class="text-xl font-semibold text-slate-900">
			{data.job.ref} — {data.job.title ?? 'Untitled'}
		</h1>
		<span class="rounded bg-slate-100 px-2 py-0.5 text-xs">{data.job.current_status}</span>
	</div>
	<p class="mt-1 text-sm text-slate-600">
		{data.job.company ?? 'Unknown company'} · {data.job.source ?? 'unknown source'} ·
		<a href={data.job.url} target="_blank" rel="noreferrer" class="underline underline-offset-2"
			>original posting ↗</a
		>
	</p>
	{#if data.job.duplicate_of_job_id}
		<p class="mt-2 rounded bg-amber-50 px-3 py-2 text-sm text-amber-800">
			Possible duplicate of <a
				href="/jobs/{data.job.duplicate_of_job_id}"
				class="underline underline-offset-2">job #{data.job.duplicate_of_job_id}</a
			>.
		</p>
	{/if}

	{#if needsEnrichment}
		<section class="mt-4 rounded border border-amber-200 bg-amber-50 p-4">
			<h2 class="text-sm font-semibold text-amber-900">
				Job description not saved yet ({data.job.capture_completeness.replace('_', ' ')})
			</h2>
			<p class="mt-1 text-xs text-amber-800">
				The link is saved. If the original page asks you to sign in or verify your browser,
				open it normally, then paste the full job description below to continue.
			</p>
			<form method="post" action="?/enrich" use:enhance class="mt-3 space-y-2">
				<textarea
					name="raw_text"
					rows="8"
					required
					class="w-full rounded border border-slate-300 px-3 py-1.5 text-sm"
					placeholder="Paste the full job description here…"
				></textarea>
				<button
					type="submit"
					class="rounded bg-slate-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
				>
					Save description
				</button>
				{#if form?.error}<p class="text-sm text-red-600">{form.error}</p>{/if}
			</form>
		</section>
	{/if}

	<section class="mt-6 rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Raw job description</h2>
		{#if data.raw?.raw_text}
			<pre class="mt-2 max-h-96 overflow-y-auto whitespace-pre-wrap text-sm text-slate-700">{data
					.raw.raw_text}</pre>
		{:else}
			<p class="mt-2 text-sm text-slate-500">No job description text saved yet.</p>
		{/if}
	</section>

	<section class="mt-6 rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Tailored CV</h2>
		<ul class="mt-2 divide-y divide-slate-100">
			{#each data.cvVersions as version (version.id)}
				<li class="flex items-center justify-between py-2 text-sm">
					<a href="/cv/{version.id}" class="underline underline-offset-2">
						CV_{data.job.ref}_v{version.version_number}
					</a>
					{#if version.is_submitted}
						<span class="rounded bg-emerald-100 px-1.5 py-0.5 text-xs text-emerald-800"
							>submitted</span
						>
					{/if}
				</li>
			{:else}
				<li class="py-2 text-sm text-slate-500">No CV generated yet.</li>
			{/each}
		</ul>
		<form method="post" action="?/generateCv" use:enhance class="mt-3">
			<button
				type="submit"
				disabled={!data.raw?.raw_text}
				class="rounded bg-slate-900 px-4 py-1.5 text-sm text-white hover:bg-slate-800 disabled:opacity-40"
			>
				{data.cvVersions.length ? 'Regenerate CV' : 'Generate CV'}
			</button>
			{#if !data.raw?.raw_text}
				<p class="mt-1 text-xs text-slate-500">Save the job description text first.</p>
			{/if}
			{#if form?.error}<p class="mt-2 text-sm text-red-600">{form.error}</p>{/if}
		</form>
	</section>

	<section class="mt-6 rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Tracking</h2>

		{#if data.job.current_status === 'SKIPPED'}
			<p class="mt-2 text-sm text-slate-600">Skipped.</p>
			<form method="post" action="?/unskip" use:enhance class="mt-2">
				<button
					type="submit"
					class="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
					>Un-skip</button
				>
			</form>
		{:else if data.job.current_status === 'REJECTED' || data.job.current_status === 'WITHDRAWN'}
			<p class="mt-2 text-sm text-slate-600">
				{data.job.current_status === 'REJECTED' ? 'Rejected.' : 'Withdrawn.'} No further actions.
			</p>
		{:else if !data.application}
			<div class="mt-2 flex flex-wrap items-end gap-2">
				<form method="post" action="?/markApplied" use:enhance class="flex flex-wrap items-end gap-2">
					{#if data.cvVersions.length}
						<div>
							<label for="cv_version_id" class="block text-xs font-medium text-slate-600"
								>Submitted CV</label
							>
							<select
								id="cv_version_id"
								name="cv_version_id"
								class="mt-1 rounded border border-slate-300 px-2 py-1.5 text-sm"
							>
								<option value="">(none)</option>
								{#each data.cvVersions as version (version.id)}
									<option value={version.id}>v{version.version_number}</option>
								{/each}
							</select>
						</div>
					{/if}
					<button
						type="submit"
						class="rounded bg-slate-900 px-4 py-1.5 text-sm text-white hover:bg-slate-800"
						>Mark as Applied</button
					>
				</form>
				{#if canSkip}
					<form method="post" action="?/skip" use:enhance>
						<button
							type="submit"
							class="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
							>Skip</button
						>
					</form>
				{/if}
			</div>
		{:else}
			<p class="mt-2 text-sm text-slate-600">
				Application #{data.application.id} — status <strong>{data.job.current_status}</strong>
			</p>
			<div class="mt-2 flex flex-wrap gap-2">
				{#each nextSteps as step (step.eventType)}
					<form method="post" action="?/addEvent" use:enhance>
						<input type="hidden" name="application_id" value={data.application.id} />
						<input type="hidden" name="event_type" value={step.eventType} />
						<button
							type="submit"
							class="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
							>{step.label}</button
						>
					</form>
				{/each}
			</div>
		{/if}
		{#if form?.error}<p class="mt-2 text-sm text-red-600">{form.error}</p>{/if}
	</section>

	<section class="mt-6 rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Correct title / company</h2>
		<form method="post" action="?/correct" use:enhance class="mt-3 flex flex-wrap gap-3">
			<div>
				<label for="title" class="block text-xs font-medium text-slate-600">Title</label>
				<input
					id="title"
					name="title"
					value={data.job.title ?? ''}
					class="mt-1 rounded border border-slate-300 px-2 py-1.5 text-sm"
				/>
			</div>
			<div>
				<label for="company" class="block text-xs font-medium text-slate-600">Company</label>
				<input
					id="company"
					name="company"
					value={data.job.company ?? ''}
					class="mt-1 rounded border border-slate-300 px-2 py-1.5 text-sm"
				/>
			</div>
			<button
				type="submit"
				class="self-end rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
			>
				Save
			</button>
		</form>
	</section>

	<section class="mt-6 rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Timeline</h2>
		<ol class="mt-3 space-y-2">
			{#each data.job.events as event, i (i)}
				<li class="flex items-center gap-3 text-sm">
					<span class="w-40 shrink-0 text-slate-400"
						>{new Date(event.occurred_at).toLocaleString()}</span
					>
					<span class="rounded bg-slate-100 px-2 py-0.5 text-xs">{event.event_type}</span>
				</li>
			{/each}
		</ol>
	</section>

	<section class="mt-6 rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Raw snapshots</h2>
		<table class="mt-3 w-full text-left text-sm">
			<thead class="text-xs uppercase text-slate-500">
				<tr>
					<th class="py-1">Captured</th>
					<th class="py-1">Method</th>
					<th class="py-1">Length</th>
				</tr>
			</thead>
			<tbody>
				{#each data.job.snapshots as snapshot (snapshot.id)}
					<tr class="border-t border-slate-100">
						<td class="py-1">{new Date(snapshot.captured_at).toLocaleString()}</td>
						<td class="py-1">{snapshot.capture_method}</td>
						<td class="py-1">{snapshot.raw_text_length} chars</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</section>
</div>
