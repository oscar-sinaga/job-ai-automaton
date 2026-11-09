<script lang="ts">
	import { appPath } from '$lib/app-path';

	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<div class="max-w-md">
	{#if data.outcome === 'success'}
		<div class="rounded border border-emerald-200 bg-emerald-50 p-4">
			<h1 class="text-lg font-semibold text-emerald-900">
				Saved as {data.capture.ref}
			</h1>
			<p class="mt-1 text-sm text-emerald-800">
				{data.capture.capture_completeness === 'CAPTURED_PARTIAL'
					? 'Only the link was shared — open the job later to paste the full description.'
					: 'Job description captured.'}
			</p>
			{#if data.capture.duplicate_of_job_id}
				<p class="mt-1 text-xs text-emerald-700">
					Possible duplicate of job #{data.capture.duplicate_of_job_id}.
				</p>
			{/if}
		</div>
		<a href={appPath(`/jobs/${data.capture.job_id}`)} class="mt-4 inline-block text-sm underline underline-offset-2"
			>Open job →</a
		>
	{:else}
		<div class="rounded border border-red-200 bg-red-50 p-4">
			<h1 class="text-lg font-semibold text-red-900">Couldn't save this job</h1>
			<p class="mt-1 text-sm text-red-800">{data.message}</p>
		</div>
	{/if}
	<a href={appPath(`/jobs`)} class="mt-4 block text-sm text-slate-500 underline underline-offset-2"
		>← Job Inbox</a
	>
</div>
