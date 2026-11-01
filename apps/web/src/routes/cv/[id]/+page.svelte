<script lang="ts">
	import { enhance } from '$app/forms';
	import type { PageProps } from './$types';

	let { data, form }: PageProps = $props();
</script>

<div class="max-w-3xl">
	<a href="/jobs/{data.cv.job_id}" class="text-sm text-slate-500 underline underline-offset-2"
		>← Job Detail</a
	>

	<div class="mt-2 flex items-center gap-3">
		<h1 class="text-xl font-semibold text-slate-900">{data.cv.label}</h1>
		{#if data.cv.is_submitted}
			<span class="rounded bg-emerald-100 px-2 py-0.5 text-xs text-emerald-800">submitted</span>
		{/if}
	</div>
	<p class="mt-1 text-xs text-slate-500">
		Every bullet below is traceable to a career fact. Removing a bullet creates a new version — this
		one stays exactly as generated.
	</p>

	{#if form?.error}
		<p class="mt-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{form.error}</p>
	{/if}
	{#if form?.success}
		<p class="mt-3 rounded bg-emerald-50 px-3 py-2 text-sm text-emerald-700">Done.</p>
	{/if}

	<!-- Summary -->
	<section class="mt-6 rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Summary</h2>
		{#if data.cv.sections.summary.text}
			<div class="mt-2 flex items-start justify-between gap-2 text-sm">
				<p>{data.cv.sections.summary.text}</p>
				<form method="post" action="?/removeBullet" use:enhance>
					<input type="hidden" name="section" value="summary" />
					<button type="submit" class="shrink-0 text-xs text-red-600 underline underline-offset-2"
						>remove</button
					>
				</form>
			</div>
			<p class="mt-1 flex flex-wrap gap-1">
				{#each data.cv.sections.summary.supporting_fact_ids as fid (fid)}
					<span class="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{fid}</span>
				{/each}
			</p>
		{:else}
			<p class="mt-2 text-sm text-slate-500">(removed)</p>
		{/if}
	</section>

	<!-- Experience -->
	{#if data.cv.sections.experience.length}
		<section class="mt-6 rounded border border-slate-200 bg-white p-4">
			<h2 class="text-sm font-semibold text-slate-900">Experience</h2>
			{#each data.cv.sections.experience as block, blockIndex (blockIndex)}
				<ul class="mt-2 space-y-2">
					{#each block.bullets as bullet, bulletIndex (bulletIndex)}
						<li class="flex items-start justify-between gap-2 text-sm">
							<div>
								<p>{bullet.text}</p>
								<p class="mt-1 flex flex-wrap gap-1">
									{#each bullet.supporting_fact_ids as fid (fid)}
										<span class="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{fid}</span>
									{/each}
								</p>
							</div>
							<form method="post" action="?/removeBullet" use:enhance>
								<input type="hidden" name="section" value="experience" />
								<input type="hidden" name="blockIndex" value={blockIndex} />
								<input type="hidden" name="bulletIndex" value={bulletIndex} />
								<button type="submit" class="shrink-0 text-xs text-red-600 underline underline-offset-2"
									>remove</button
								>
							</form>
						</li>
					{/each}
				</ul>
			{/each}
		</section>
	{/if}

	<!-- Projects -->
	{#if data.cv.sections.projects.length}
		<section class="mt-6 rounded border border-slate-200 bg-white p-4">
			<h2 class="text-sm font-semibold text-slate-900">Projects</h2>
			{#each data.cv.sections.projects as block, blockIndex (blockIndex)}
				<ul class="mt-2 space-y-2">
					{#each block.bullets as bullet, bulletIndex (bulletIndex)}
						<li class="flex items-start justify-between gap-2 text-sm">
							<p>{bullet.text}</p>
							<form method="post" action="?/removeBullet" use:enhance>
								<input type="hidden" name="section" value="projects" />
								<input type="hidden" name="blockIndex" value={blockIndex} />
								<input type="hidden" name="bulletIndex" value={bulletIndex} />
								<button type="submit" class="shrink-0 text-xs text-red-600 underline underline-offset-2"
									>remove</button
								>
							</form>
						</li>
					{/each}
				</ul>
			{/each}
		</section>
	{/if}

	<!-- Skills -->
	{#if data.cv.sections.skills.length}
		<section class="mt-6 rounded border border-slate-200 bg-white p-4">
			<h2 class="text-sm font-semibold text-slate-900">Skills</h2>
			<p class="mt-2 text-sm">{data.cv.sections.skills.join(', ')}</p>
		</section>
	{/if}

	<!-- Missing requirements -->
	{#if data.cv.sections.missing_requirements.length}
		<section class="mt-6 rounded border border-amber-200 bg-amber-50 p-4">
			<h2 class="text-sm font-semibold text-amber-900">Requirements this CV doesn't cover</h2>
			<ul class="mt-2 list-inside list-disc text-sm text-amber-800">
				{#each data.cv.sections.missing_requirements as req (req)}
					<li>{req}</li>
				{/each}
			</ul>
		</section>
	{/if}

	<!-- Actions -->
	<section class="mt-6 flex flex-wrap gap-2 rounded border border-slate-200 bg-white p-4">
		<form method="post" action="?/approve" use:enhance>
			<button type="submit" class="rounded bg-slate-900 px-4 py-1.5 text-sm text-white hover:bg-slate-800"
				>Approve (job → Ready to Apply)</button
			>
		</form>
		<form method="post" action="?/export" use:enhance>
			<button type="submit" class="rounded border border-slate-300 px-4 py-1.5 text-sm hover:bg-slate-50"
				>Export PDF</button
			>
		</form>
		{#if !data.cv.is_submitted}
			<form method="post" action="?/markSubmitted" use:enhance>
				<button type="submit" class="rounded border border-slate-300 px-4 py-1.5 text-sm hover:bg-slate-50"
					>Mark as submitted</button
				>
			</form>
		{/if}
	</section>
</div>
