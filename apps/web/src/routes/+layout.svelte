<script lang="ts">
	import { onMount } from 'svelte';
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import { page } from '$app/state';
	import { NAV_ITEMS } from '$lib/nav';

	let { children } = $props();

	// Some platforms require an active service worker for PWA installability
	// and Web Share Target eligibility (docs/09 §3, ADR-020).
	onMount(() => {
		if ('serviceWorker' in navigator) {
			navigator.serviceWorker.register('/sw.js').catch(() => {
				/* not fatal -- the app works fully without it */
			});
		}
	});
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>

<div class="min-h-screen bg-slate-50 text-slate-900">
	<div class="flex min-h-screen">
		<!-- NFR-001: functional, keyboard-reachable nav; no design system (docs/01 §9). -->
		<nav class="w-56 shrink-0 border-r border-slate-200 bg-white p-4">
			<a href="/" class="mb-6 block text-sm font-semibold tracking-tight text-slate-900">
				OSCAR Job Copilot
			</a>
			<ul class="space-y-1">
				{#each NAV_ITEMS as item (item.href)}
					{@const active = page.url.pathname === item.href}
					<li>
						<a
							href={item.href}
							class="block rounded px-3 py-2 text-sm {active
								? 'bg-slate-900 text-white'
								: 'text-slate-700 hover:bg-slate-100'}"
						>
							{item.label}
						</a>
					</li>
				{/each}
			</ul>
			<p class="mt-8 text-xs text-slate-400">
				Milestone 5 — analytics.<br />All P0 milestones built. See docs/15.
			</p>
		</nav>
		<main class="min-w-0 flex-1 p-8">
			{@render children()}
		</main>
	</div>
</div>
