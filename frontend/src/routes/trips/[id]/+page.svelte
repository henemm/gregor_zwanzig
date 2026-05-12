<script lang="ts">
	import { page } from '$app/state';
	import TripTabs from '$lib/components/trip-detail/TripTabs.svelte';

	let { data } = $props();

	// Initial-Tab aus URL-Hash. $derived bleibt reaktiv falls user navigation triggert.
	const initialTab = $derived((page.url.hash || '').replace(/^#/, '') || 'overview');
</script>

<svelte:head><title>{data.trip.name} — Gregor 20</title></svelte:head>

<main class="container mx-auto max-w-5xl p-4">
	<h1 class="mb-4 text-2xl font-bold">{data.trip.name}</h1>
	<TripTabs {initialTab} badges={{}} />
</main>
