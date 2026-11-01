<script lang="ts">
	interface Props {
		title: string;
		milestone: string;
		docHref: string;
		description: string;
	}

	let { title, milestone, docHref, description }: Props = $props();
</script>

<div class="max-w-2xl">
	<h1 class="text-xl font-semibold text-slate-900">{title}</h1>
	<p class="mt-2 text-sm text-slate-600">{description}</p>
	<div class="mt-4 rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
		Not implemented yet — planned for <strong>{milestone}</strong>. Design:
		<code class="text-xs">{docHref}</code>.
	</div>
</div>
