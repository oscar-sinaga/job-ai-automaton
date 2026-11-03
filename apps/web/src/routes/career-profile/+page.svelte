<script lang="ts">
	import { enhance } from '$app/forms';
	import type { PageProps } from './$types';

	let { data, form }: PageProps = $props();
</script>

{#snippet sectionError()}
	{#if form?.error}
		<p class="mt-2 text-sm text-red-600">{form.error}</p>
	{/if}
{/snippet}

<div class="max-w-3xl space-y-8">
	<div>
		<h1 class="text-xl font-semibold text-slate-900">Career Profile</h1>
		<p class="mt-1 text-sm text-slate-600">
			The single source of truth for CV generation (Milestone 3). Every achievement below will
			become a citable fact — see <code class="text-xs">docs/07_CV_GROUNDING_AND_EVALS.md</code>.
		</p>
	</div>

	<!-- Summary -->
	<section class="rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Summary</h2>
		<form method="post" action="?/updateSummary" use:enhance={() => ({ update }) => update({ reset: false })} class="mt-2 space-y-2">
			<textarea
				name="summary"
				rows="3"
				class="w-full rounded border border-slate-300 px-3 py-1.5 text-sm"
				>{data.profile.summary ?? ''}</textarea
			>
			<button
				type="submit"
				class="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
			>
				Save
			</button>
		</form>
	</section>

	<!-- Experiences -->
	<section class="rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Experience</h2>
		<ul class="mt-2 divide-y divide-slate-100">
			{#each data.profile.experiences as exp (exp.id)}
				<li class="flex items-center justify-between py-2 text-sm">
					<div>
						<span class="font-medium">{exp.title}</span> at {exp.company}
						<span class="text-slate-500"
							>({exp.start_date} – {exp.is_current ? 'present' : (exp.end_date ?? '?')})</span
						>
					</div>
					<form method="post" action="?/deleteExperience" use:enhance>
						<input type="hidden" name="id" value={exp.id} />
						<button type="submit" class="text-xs text-red-600 underline underline-offset-2"
							>remove</button
						>
					</form>
				</li>
			{:else}
				<li class="py-2 text-sm text-slate-500">None yet.</li>
			{/each}
		</ul>
		<form
			method="post"
			action="?/addExperience"
			use:enhance
			class="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2 border-t border-slate-100 pt-3"
		>
			<input name="company" placeholder="Company" required class="rounded border px-2 py-1 text-sm" />
			<input name="title" placeholder="Title" required class="rounded border px-2 py-1 text-sm" />
			<input name="location" placeholder="Location" class="rounded border px-2 py-1 text-sm" />
			<input
				name="start_date"
				type="date"
				required
				class="rounded border px-2 py-1 text-sm"
				aria-label="Start date"
			/>
			<input name="end_date" type="date" class="rounded border px-2 py-1 text-sm" aria-label="End date" />
			<label class="flex items-center gap-1 text-sm text-slate-600">
				<input type="checkbox" name="is_current" /> Current role
			</label>
			<textarea
				name="description"
				placeholder="Description (optional)"
				class="sm:col-span-2 rounded border px-2 py-1 text-sm"
			></textarea>
			<button
				type="submit"
				class="sm:col-span-2 rounded bg-slate-900 px-3 py-1.5 text-sm text-white hover:bg-slate-800"
				>Add experience</button
			>
		</form>
		{@render sectionError()}
	</section>

	<!-- Projects -->
	<section class="rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Projects</h2>
		<ul class="mt-2 divide-y divide-slate-100">
			{#each data.profile.projects as project (project.id)}
				<li class="flex items-center justify-between py-2 text-sm">
					<span class="font-medium">{project.name}</span>
					<form method="post" action="?/deleteProject" use:enhance>
						<input type="hidden" name="id" value={project.id} />
						<button type="submit" class="text-xs text-red-600 underline underline-offset-2"
							>remove</button
						>
					</form>
				</li>
			{:else}
				<li class="py-2 text-sm text-slate-500">None yet.</li>
			{/each}
		</ul>
		<form
			method="post"
			action="?/addProject"
			use:enhance
			class="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2 border-t border-slate-100 pt-3"
		>
			<input name="name" placeholder="Project name" required class="rounded border px-2 py-1 text-sm" />
			<input name="link" placeholder="Link (optional)" class="rounded border px-2 py-1 text-sm" />
			<textarea
				name="description"
				placeholder="Description"
				class="sm:col-span-2 rounded border px-2 py-1 text-sm"
			></textarea>
			<button
				type="submit"
				class="sm:col-span-2 rounded bg-slate-900 px-3 py-1.5 text-sm text-white hover:bg-slate-800"
				>Add project</button
			>
		</form>
	</section>

	<!-- Achievements -->
	<section class="rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Achievements</h2>
		<p class="mt-1 text-xs text-slate-500">
			A verified metric requires a value — an unverified one may state a fact but never a number
			once CVs are generated.
		</p>
		<ul class="mt-2 divide-y divide-slate-100">
			{#each data.profile.achievements as ach (ach.id)}
				<li class="py-2 text-sm">
					<div class="flex items-start justify-between gap-2">
						<div>
							<p>{ach.statement}</p>
							{#if ach.metric_value}
								<p class="text-xs text-slate-500">
									{ach.metric_value}
									{ach.metric_verified ? '(verified)' : '(unverified — not usable as a number)'}
								</p>
							{/if}
							{#if ach.skill_tags.length}
								<p class="mt-1 flex flex-wrap gap-1">
									{#each ach.skill_tags as tag (tag)}
										<span class="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{tag}</span>
									{/each}
								</p>
							{/if}
						</div>
						<form method="post" action="?/deleteAchievement" use:enhance>
							<input type="hidden" name="id" value={ach.id} />
							<button type="submit" class="shrink-0 text-xs text-red-600 underline underline-offset-2"
								>remove</button
							>
						</form>
					</div>
				</li>
			{:else}
				<li class="py-2 text-sm text-slate-500">None yet.</li>
			{/each}
		</ul>
		<form
			method="post"
			action="?/addAchievement"
			use:enhance
			class="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2 border-t border-slate-100 pt-3"
		>
			<textarea
				name="statement"
				placeholder="What did you do? (in your own words)"
				required
				class="sm:col-span-2 rounded border px-2 py-1 text-sm"
			></textarea>
			<select name="experience_id" class="rounded border px-2 py-1 text-sm">
				<option value="">(no linked experience)</option>
				{#each data.profile.experiences as exp (exp.id)}
					<option value={exp.id}>{exp.title} @ {exp.company}</option>
				{/each}
			</select>
			<select name="project_id" class="rounded border px-2 py-1 text-sm">
				<option value="">(no linked project)</option>
				{#each data.profile.projects as project (project.id)}
					<option value={project.id}>{project.name}</option>
				{/each}
			</select>
			<input
				name="metric_value"
				placeholder="Metric (e.g. reduced latency 320ms→90ms)"
				class="rounded border px-2 py-1 text-sm"
			/>
			<label class="flex items-center gap-1 text-sm text-slate-600">
				<input type="checkbox" name="metric_verified" /> Metric verified
			</label>
			<input name="skill_tags" placeholder="skill tags (comma-separated)" class="rounded border px-2 py-1 text-sm" />
			<input
				name="technology_tags"
				placeholder="technology tags (comma-separated)"
				class="rounded border px-2 py-1 text-sm"
			/>
			<input
				name="domain_tags"
				placeholder="domain tags (comma-separated)"
				class="sm:col-span-2 rounded border px-2 py-1 text-sm"
			/>
			<button
				type="submit"
				class="sm:col-span-2 rounded bg-slate-900 px-3 py-1.5 text-sm text-white hover:bg-slate-800"
				>Add achievement</button
			>
		</form>
		{@render sectionError()}
	</section>

	<!-- Skills -->
	<section class="rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Skills</h2>
		<ul class="mt-2 flex flex-wrap gap-2">
			{#each data.profile.skills as skill (skill.id)}
				<li class="flex items-center gap-1 rounded bg-slate-100 px-2 py-1 text-xs">
					{skill.name}{skill.years_experience ? ` (${skill.years_experience}y)` : ''}
					<form method="post" action="?/deleteSkill" use:enhance>
						<input type="hidden" name="id" value={skill.id} />
						<button type="submit" class="text-red-600">×</button>
					</form>
				</li>
			{:else}
				<li class="text-sm text-slate-500">None yet.</li>
			{/each}
		</ul>
		<form method="post" action="?/addSkill" use:enhance class="mt-3 flex flex-wrap gap-2">
			<input name="name" placeholder="Skill" required class="rounded border px-2 py-1 text-sm" />
			<input name="category" placeholder="Category" class="rounded border px-2 py-1 text-sm" />
			<input
				name="years_experience"
				type="number"
				step="0.5"
				placeholder="Years"
				class="w-20 rounded border px-2 py-1 text-sm"
			/>
			<button type="submit" class="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
				>Add</button
			>
		</form>
	</section>

	<!-- Education -->
	<section class="rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Education</h2>
		<ul class="mt-2 divide-y divide-slate-100">
			{#each data.profile.education as edu (edu.id)}
				<li class="flex items-center justify-between py-2 text-sm">
					{edu.institution}{edu.degree ? ` — ${edu.degree}` : ''}
					<form method="post" action="?/deleteEducation" use:enhance>
						<input type="hidden" name="id" value={edu.id} />
						<button type="submit" class="text-xs text-red-600 underline underline-offset-2"
							>remove</button
						>
					</form>
				</li>
			{:else}
				<li class="py-2 text-sm text-slate-500">None yet.</li>
			{/each}
		</ul>
		<form method="post" action="?/addEducation" use:enhance class="mt-3 flex flex-wrap gap-2">
			<input name="institution" placeholder="Institution" required class="rounded border px-2 py-1 text-sm" />
			<input name="degree" placeholder="Degree" class="rounded border px-2 py-1 text-sm" />
			<input name="field" placeholder="Field" class="rounded border px-2 py-1 text-sm" />
			<button type="submit" class="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
				>Add</button
			>
		</form>
	</section>

	<!-- Certifications -->
	<section class="rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Certifications</h2>
		<ul class="mt-2 divide-y divide-slate-100">
			{#each data.profile.certifications as cert (cert.id)}
				<li class="flex items-center justify-between py-2 text-sm">
					{cert.name}{cert.issuer ? ` — ${cert.issuer}` : ''}
					<form method="post" action="?/deleteCertification" use:enhance>
						<input type="hidden" name="id" value={cert.id} />
						<button type="submit" class="text-xs text-red-600 underline underline-offset-2"
							>remove</button
						>
					</form>
				</li>
			{:else}
				<li class="py-2 text-sm text-slate-500">None yet.</li>
			{/each}
		</ul>
		<form method="post" action="?/addCertification" use:enhance class="mt-3 flex flex-wrap gap-2">
			<input name="name" placeholder="Certification" required class="rounded border px-2 py-1 text-sm" />
			<input name="issuer" placeholder="Issuer" class="rounded border px-2 py-1 text-sm" />
			<button type="submit" class="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
				>Add</button
			>
		</form>
	</section>

	<!-- Application profile -->
	<section class="rounded border border-slate-200 bg-white p-4">
		<h2 class="text-sm font-semibold text-slate-900">Application preferences</h2>
		<form
			method="post"
			action="?/updateApplicationProfile"
			use:enhance={() => ({ update }) => update({ reset: false })}
			class="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2"
		>
			<p class="sm:col-span-2 text-xs text-slate-500">CV contact details are saved with each new CV version. Name and email are required for PDF export.</p>
			{#each ['name', 'email', 'phone', 'linkedin', 'github', 'portfolio', 'location'] as field (field)}
				<label class="text-xs text-slate-600">
					CV {field}
					<input
						name={`cv_${field}`}
						type={field === 'email' ? 'email' : 'text'}
						value={String(data.profile.application_profile.links[`cv_${field}`] ?? '')}
						class="mt-1 w-full rounded border px-2 py-1 text-sm"
					/>
				</label>
			{/each}
			<input
				name="notice_period"
				placeholder="Notice period"
				value={data.profile.application_profile.notice_period ?? ''}
				class="rounded border px-2 py-1 text-sm"
			/>
			<input
				name="salary_expectation"
				placeholder="Salary expectation"
				value={data.profile.application_profile.salary_expectation ?? ''}
				class="rounded border px-2 py-1 text-sm"
			/>
			<input
				name="work_authorization"
				placeholder="Work authorization"
				value={data.profile.application_profile.work_authorization ?? ''}
				class="rounded border px-2 py-1 text-sm"
			/>
			<input
				name="preferred_location"
				placeholder="Preferred location"
				value={data.profile.application_profile.preferred_location ?? ''}
				class="rounded border px-2 py-1 text-sm"
			/>
			<label class="sm:col-span-2 flex items-center gap-1 text-sm text-slate-600">
				<!-- An unchecked checkbox submits nothing at all, so a plain
				     checkbox can set relocation_ok=true but never explicitly
				     back to false; this hidden marker lets the action tell
				     "left unchanged" apart from "unchecked". -->
				<input type="hidden" name="relocation_ok_present" value="1" />
				<input
					type="checkbox"
					name="relocation_ok"
					checked={data.profile.application_profile.relocation_ok ?? false}
				/> Open to relocation
			</label>
			<button
				type="submit"
				class="sm:col-span-2 rounded bg-slate-900 px-3 py-1.5 text-sm text-white hover:bg-slate-800"
				>Save preferences</button
			>
		</form>
	</section>
</div>

<style>
	input, textarea, select {
		min-width: 0;
		max-width: 100%;
	}
</style>
