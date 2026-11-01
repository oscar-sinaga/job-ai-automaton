<script lang="ts">
	import { enhance } from '$app/forms';
	import type { PageProps } from './$types';

	let { data, form }: PageProps = $props();

	let showPasteText = $state(false);

	const STATUSES = [
		'SAVED',
		'READY_TO_APPLY',
		'APPLYING',
		'APPLIED',
		'ASSESSMENT',
		'INTERVIEW',
		'FINAL_INTERVIEW',
		'OFFER',
		'REJECTED',
		'WITHDRAWN',
		'SKIPPED'
	];

	function completenessLabel(value: string): string {
		return value.replace('CAPTURED_', '').replace('_', ' ');
	}
</script>

<div class="max-w-5xl">
	<h1 class="text-xl font-semibold text-slate-900">Job Inbox</h1>
	<p class="mt-1 text-sm text-slate-600">
		{data.jobs.items.length} job{data.jobs.items.length === 1 ? '' : 's'} shown.
	</p>

	<!-- Manual URL / paste-text capture (docs/08 §7) -- works without the extension. -->
	<section class="mt-6 rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Save a job</h2>
		<form
			method="post"
			action="?/capture"
			use:enhance
			class="mt-3 space-y-3"
		>
			<div>
				<label for="url" class="block text-xs font-medium text-slate-600">Job URL</label>
				<input
					id="url"
					name="url"
					type="url"
					required
					placeholder="https://..."
					class="mt-1 w-full rounded border border-slate-300 px-3 py-1.5 text-sm"
				/>
			</div>
			<button
				type="button"
				class="text-xs text-slate-600 underline underline-offset-2"
				onclick={() => (showPasteText = !showPasteText)}
			>
				{showPasteText ? 'Hide' : 'Paste full job description (recommended)'}
			</button>
			{#if showPasteText}
				<div>
					<label for="raw_text" class="block text-xs font-medium text-slate-600"
						>Job description text</label
					>
					<textarea
						id="raw_text"
						name="raw_text"
						rows="6"
						class="mt-1 w-full rounded border border-slate-300 px-3 py-1.5 text-sm"
					></textarea>
				</div>
			{/if}
			<button
				type="submit"
				class="rounded bg-slate-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
			>
				Save job
			</button>
			{#if form?.error}
				<p class="text-sm text-red-600">{form.error}</p>
			{/if}
			{#if form?.success}
				<p class="text-sm text-emerald-600">Saved.</p>
			{/if}
		</form>
	</section>

	<!-- Filters -->
	<form method="get" class="mt-6 flex flex-wrap items-end gap-3">
		<div>
			<label for="status" class="block text-xs font-medium text-slate-600">Status</label>
			<select
				id="status"
				name="status"
				value={data.status}
				class="mt-1 rounded border border-slate-300 px-2 py-1.5 text-sm"
			>
				<option value="">All</option>
				{#each STATUSES as status (status)}
					<option value={status}>{status}</option>
				{/each}
			</select>
		</div>
		<div>
			<label for="source" class="block text-xs font-medium text-slate-600">Source</label>
			<input
				id="source"
				name="source"
				value={data.source}
				placeholder="linkedin.com"
				class="mt-1 rounded border border-slate-300 px-2 py-1.5 text-sm"
			/>
		</div>
		<div>
			<label for="q" class="block text-xs font-medium text-slate-600">Search title</label>
			<input
				id="q"
				name="q"
				value={data.q}
				class="mt-1 rounded border border-slate-300 px-2 py-1.5 text-sm"
			/>
		</div>
		<button
			type="submit"
			class="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
		>
			Filter
		</button>
	</form>

	<!-- Job list -->
	<div class="mt-4 overflow-x-auto rounded border border-slate-200 bg-white">
		<table class="w-full text-left text-sm">
			<thead class="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
				<tr>
					<th class="px-3 py-2">Ref</th>
					<th class="px-3 py-2">Title</th>
					<th class="px-3 py-2">Company</th>
					<th class="px-3 py-2">Source</th>
					<th class="px-3 py-2">Status</th>
					<th class="px-3 py-2">Capture</th>
					<th class="px-3 py-2">Saved</th>
				</tr>
			</thead>
			<tbody>
				{#each data.jobs.items as job (job.id)}
					<tr class="border-b border-slate-100 last:border-0 hover:bg-slate-50">
						<td class="px-3 py-2">
							<a href="/jobs/{job.id}" class="font-medium text-slate-900 underline underline-offset-2"
								>{job.ref}</a
							>
							{#if job.is_duplicate}
								<span class="ml-1 rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-800"
									>dup</span
								>
							{/if}
						</td>
						<td class="px-3 py-2">{job.title ?? '—'}</td>
						<td class="px-3 py-2">{job.company ?? '—'}</td>
						<td class="px-3 py-2">{job.source ?? '—'}</td>
						<td class="px-3 py-2">
							<span class="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{job.current_status}</span>
						</td>
						<td class="px-3 py-2">
							<span
								class="rounded px-1.5 py-0.5 text-xs {job.capture_completeness === 'CAPTURED_COMPLETE'
									? 'bg-emerald-100 text-emerald-800'
									: job.capture_completeness === 'CAPTURED_PARTIAL'
										? 'bg-slate-100 text-slate-600'
										: 'bg-amber-100 text-amber-800'}"
							>
								{completenessLabel(job.capture_completeness)}
							</span>
						</td>
						<td class="px-3 py-2 text-slate-500">
							{new Date(job.created_at).toLocaleDateString()}
						</td>
					</tr>
				{:else}
					<tr>
						<td colspan="7" class="px-3 py-6 text-center text-slate-500">
							No jobs yet. Save one above.
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>

	{#if data.jobs.next_cursor}
		<a
			href="?cursor={data.jobs.next_cursor}"
			class="mt-3 inline-block text-sm text-slate-600 underline underline-offset-2"
		>
			Next page →
		</a>
	{/if}
</div>
