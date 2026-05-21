<script lang="ts">
	import type { Trip, Subscription } from '$lib/types.js';
	import { Btn } from '$lib/components/ui/btn/index.js';
	import { Eyebrow } from '$lib/components/ui/eyebrow/index.js';
	import TripKachel from './_home/TripKachel.svelte';
	import CompareKachel from './_home/CompareKachel.svelte';
	import EmptyKachel from './_home/EmptyKachel.svelte';

	let { data } = $props();

	const trips = $derived((data.trips ?? []) as Trip[]);
	const subscriptions = $derived((data.subscriptions ?? []) as Subscription[]);
	const isEmpty = $derived(trips.length === 0 && subscriptions.length === 0);
	const todayPretty = new Date().toLocaleDateString('de-DE', {
		day: 'numeric',
		month: 'long',
		year: 'numeric'
	});
</script>

<div class="home">
	<header class="home__header">
		<Eyebrow>{todayPretty}</Eyebrow>
		<h1 class="home__title">Startseite</h1>
	</header>

	{#if isEmpty}
		<EmptyKachel />
	{:else}
		{#if trips.length > 0}
			<section>
				<h2 class="home__section-title">Meine Touren</h2>
				<div class="kachel-grid">
					{#each trips as trip (trip.id)}
						<TripKachel {trip} />
					{/each}
				</div>
			</section>
		{/if}

		{#if subscriptions.length > 0}
			<section>
				<h2 class="home__section-title">Orts-Vergleiche</h2>
				<div class="kachel-grid">
					{#each subscriptions as sub (sub.id)}
						<CompareKachel {sub} />
					{/each}
				</div>
			</section>
		{/if}

		<div class="home__cta">
			<Btn href="/trips/new" variant="accent">+ Neue Tour</Btn>
			<Btn href="/compare" variant="outline">+ Neuer Vergleich</Btn>
		</div>
	{/if}
</div>

<style>
	.home { display: flex; flex-direction: column; gap: 2rem; }
	.home__header { display: flex; flex-direction: column; gap: 0.25rem; }
	.home__title { font-size: var(--g-text-3xl); font-weight: 600; margin: 0; }
	.home__section-title { font-size: var(--g-text-xl); font-weight: 600; margin: 0 0 0.75rem; }
	.kachel-grid { display: grid; grid-template-columns: 1fr; gap: 0.75rem; }
	@media (min-width: 640px) { .kachel-grid { grid-template-columns: repeat(2, 1fr); } }
	@media (min-width: 1024px) { .kachel-grid { grid-template-columns: repeat(3, 1fr); } }
	.home__cta { display: flex; gap: 0.75rem; flex-wrap: wrap; }
</style>
