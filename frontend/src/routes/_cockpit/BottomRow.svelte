<script lang="ts">
	import { GCard } from '$lib/components/ui/g-card';
	import { Eyebrow } from '$lib/components/ui/eyebrow';
	import { ElevSparkline } from '$lib/components/ui/elev-sparkline';
	import type { Trip, Stage } from '$lib/types.js';

	interface Props {
		tomorrowStage: Stage | null;
		archivedTrips: Trip[];
	}

	let { tomorrowStage, archivedTrips }: Props = $props();

	const tomorrowElev = $derived(
		tomorrowStage?.waypoints
			?.map((w) => w.elevation_m)
			.filter((e): e is number => typeof e === 'number' && Number.isFinite(e)) ?? []
	);
</script>

<div data-testid="bottom-row" class="grid grid-cols-1 md:grid-cols-2 gap-4">
	<GCard class="p-6">
		<Eyebrow>Morgen</Eyebrow>
		{#if tomorrowStage}
			<h3 class="text-base font-semibold mt-2">{tomorrowStage.name ?? tomorrowStage.date}</h3>
			<div class="text-foreground mt-2">
				<ElevSparkline data={tomorrowElev} width={200} height={32} />
			</div>
		{:else}
			<p class="text-muted-foreground mt-2 text-sm">Keine Vorschau verfügbar</p>
		{/if}
	</GCard>

	<GCard class="p-6">
		<Eyebrow>Archiv</Eyebrow>
		{#if archivedTrips.length > 0}
			<div class="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
				{#each archivedTrips as trip (trip.id)}
					<a
						data-testid="archive-trip-tile"
						href={`/trips`}
						class="block p-3 rounded border border-border hover:bg-muted/30 transition-colors"
					>
						<p class="text-sm font-medium">{trip.name}</p>
						<p class="text-xs text-muted-foreground">
							{trip.stages?.length ?? 0}
							{(trip.stages?.length ?? 0) === 1 ? 'Etappe' : 'Etappen'}
						</p>
					</a>
				{/each}
			</div>
		{:else}
			<p class="text-muted-foreground mt-2 text-sm">Keine abgeschlossenen Trips</p>
		{/if}
	</GCard>
</div>
