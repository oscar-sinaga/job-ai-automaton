<script lang="ts">
	import { appPath } from '$lib/app-path';

	import { enhance } from '$app/forms';
	import type { PageProps } from './$types';

	let { data, form }: PageProps = $props();
</script>

<div class="max-w-3xl">
	<a href={appPath(`/jobs/${data.cv.job_id}`)} class="text-sm text-slate-500 underline underline-offset-2"
		>← Job Detail</a
	>

	<div class="mt-2 flex items-center gap-3">
		<h1 class="text-xl font-semibold text-slate-900">{data.cv.label}</h1>
		{#if data.cv.is_submitted}
			<span class="rounded bg-emerald-100 px-2 py-0.5 text-xs text-emerald-800">submitted</span>
		{/if}
	</div>
	<p class="mt-1 text-xs text-slate-500">
		Check this CV against the career facts below before approving it. Removing a bullet saves a new
		version; the original stays available.
	</p>

	{#if form?.error}
		<p class="mt-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{form.error}</p>
	{/if}
	{#if form?.success}
		<p class="mt-3 rounded bg-emerald-50 px-3 py-2 text-sm text-emerald-700">Done.</p>
	{/if}
	{#if form && 'downloadUrl' in form && form.downloadUrl}
		<a href={appPath(form.downloadUrl)} download class="mt-3 inline-block rounded bg-emerald-700 px-4 py-2 text-sm text-white">Download PDF</a>
	{/if}

	<section class="mt-6 rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">CV contact details</h2>
		<p class="mt-2 text-sm">{data.cv.sections.candidate?.name ?? 'Name not set'} · {data.cv.sections.candidate?.email ?? 'Email not set'}</p>
		{#if data.cv.sections.candidate?.location}<p class="text-sm text-slate-500">{data.cv.sections.candidate.location}</p>{/if}
		<p class="mt-2 text-xs text-slate-500">Edit contact details in <a href={appPath(`/career-profile`)} class="underline">Career Profile</a>, then update this CV to save a new version.</p>
		<form method="post" action="?/refreshProfile" use:enhance class="mt-2">
			<button class="text-xs underline" type="submit">Update CV from profile</button>
		</form>
	</section>

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
				<p class="mt-3 text-sm font-medium">{block.title ?? 'Experience'}{block.company ? ` | ${block.company}` : ''}</p>
				{#if block.start_date}<p class="text-xs text-slate-500">{block.start_date} – {block.is_current ? 'Present' : (block.end_date ?? '')}</p>{/if}
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
				<p class="mt-3 text-sm font-medium">{block.name ?? 'Project'}</p>
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

	{#if data.cv.sections.education?.length}
		<section class="mt-6 rounded border border-slate-200 bg-white p-4">
			<h2 class="text-sm font-semibold text-slate-900">Education</h2>
			{#each data.cv.sections.education as item, index (index)}
				<div class="mt-2 text-sm">
					<p class="font-medium">{item.institution}</p>
					<p>{[item.degree, item.field].filter(Boolean).join(' | ')}</p>
					<p class="text-xs text-slate-500">{[item.start_date, item.end_date].filter(Boolean).join(' – ')}</p>
				</div>
			{/each}
		</section>
	{/if}
	{#if data.cv.sections.certifications?.length}
		<section class="mt-6 rounded border border-slate-200 bg-white p-4">
			<h2 class="text-sm font-semibold text-slate-900">Certifications</h2>
			{#each data.cv.sections.certifications as item, index (index)}
				<p class="mt-2 text-sm">{item.name}{item.issuer ? ` | ${item.issuer}` : ''}{item.issued_date ? ` (${item.issued_date})` : ''}</p>
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
			<h2 class="text-sm font-semibold text-amber-900">Requirements to check</h2>
			<p class="mt-2 text-xs text-amber-800">Suggested review points for this vacancy. Check your full profile and the employer's wording; equivalent skills or qualifications may satisfy a requirement.</p>
			<ul class="mt-2 list-inside list-disc text-sm text-amber-800">
				{#each data.cv.sections.missing_requirements as req (req)}
					<li>{req}</li>
				{/each}
			</ul>
		</section>
	{/if}

	<section class="mt-6 rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Career facts used in this version</h2>
		{#each Object.entries(data.cv.sections.source_facts ?? {}) as [factId, statement] (factId)}
			<div class="mt-3 text-sm"><span class="font-mono text-xs text-slate-500">{factId}</span><p>{statement}</p></div>
		{:else}
			<p class="mt-2 text-sm text-amber-800">This older version has no saved source text. Update the CV from your profile and check the sources before exporting.</p>
		{/each}
	</section>

	<!-- Actions -->
	<section class="mt-6 flex flex-wrap gap-2 rounded border border-slate-200 bg-white p-4">
		{#if !data.cv.is_approved}
			<form method="post" action="?/approve" use:enhance class="w-full space-y-3">
				<label class="flex items-start gap-2 text-sm"><input type="checkbox" name="reviewed" required class="mt-1" /> I reviewed the CV, skills and source facts, and confirm they accurately describe my experience.</label>
				<button type="submit" class="rounded bg-slate-900 px-4 py-1.5 text-sm text-white hover:bg-slate-800">Approve CV</button>
			</form>
		{:else}
			<p class="w-full text-sm text-emerald-800">This version has been reviewed and approved.</p>
		{/if}
		<form method="post" action="?/export" use:enhance>
			<button disabled={!data.cv.is_approved} type="submit" class="rounded border border-slate-300 px-4 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50"
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
