<script lang="ts">
	import { page } from '$app/state';
	import { TripHeader, TripTabs } from '$lib/components/trip-detail';
	import type { Trip } from '$lib/types';

	let { data } = $props();

	// Trip in lokales $state heben, damit Status-Updates (Pause/Archive)
	// reaktiv ohne Page-Reload sichtbar werden (Spec §7).
	let trip = $state<Trip>(data.trip);

	// Initial-Tab aus URL-Hash. $derived bleibt reaktiv falls user navigation triggert.
	const initialTab = $derived((page.url.hash || '').replace(/^#/, '') || 'overview');

	function handleStatusChange(updated: Trip): void {
		trip = updated;
	}
</script>

<svelte:head><title>{trip.name} — Gregor 20</title></svelte:head>

<main class="container mx-auto max-w-5xl p-4">
	<TripHeader {trip} onStatusChange={handleStatusChange} />
	<TripTabs {initialTab} badges={{}} />
</main>
