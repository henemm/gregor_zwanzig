<script lang="ts">
	import { GCard } from '$lib/components/ui/g-card';
	import { Pill } from '$lib/components/ui/pill';
	import { TopoBg } from '$lib/components/ui/topo';
	import { ElevSparkline } from '$lib/components/ui/elev-sparkline';
	import { Eyebrow } from '$lib/components/ui/eyebrow';
	import type { Trip, Stage } from '$lib/types.js';

	interface ForecastSummary {
		temp: number | null;
		wind: number | null;
		precip: number | null;
	}

	interface Props {
		trip: Trip;
		todayStage: Stage;
		dayIndex: number;
		forecastSummary?: ForecastSummary | null;
		forecastStatus?: 'idle' | 'loading' | 'ok' | 'error';
	}

	let {
		trip,
		todayStage,
		dayIndex,
		forecastSummary = null,
		forecastStatus = 'idle'
	}: Props = $props();

	const elevData = $derived(
		todayStage?.waypoints
			?.map((w) => w.elevation_m)
			.filter((e): e is number => typeof e === 'number' && Number.isFinite(e)) ?? []
	);

	const totalStages = $derived(trip.stages?.length ?? 0);
</script>

<div data-testid="active-trip-card">
	<GCard class="p-0 overflow-hidden">
		<TopoBg>
			<div class="p-6 space-y-3">
				<Eyebrow>Aktiver Trip</Eyebrow>
				<div class="flex items-center justify-between gap-3 flex-wrap">
					<h2 class="text-xl font-bold">{trip.name}</h2>
					<span data-testid="status-pill">
						<Pill tone="accent">
							Live · Tag {dayIndex + 1} von {totalStages}
						</Pill>
					</span>
				</div>
				{#if todayStage?.name}
					<p class="text-sm text-muted-foreground">{todayStage.name}</p>
				{/if}
				<div class="text-foreground">
					<ElevSparkline data={elevData} width={200} height={32} active={true} />
				</div>
				<p class="text-sm text-muted-foreground">
					{#if forecastStatus === 'loading'}
						Wetter wird geladen…
					{:else if forecastSummary}
						{forecastSummary.temp != null ? `${forecastSummary.temp}°C` : '—'} ·
						{forecastSummary.wind != null ? `${forecastSummary.wind} km/h Wind` : '—'} ·
						{forecastSummary.precip != null ? `${forecastSummary.precip} mm` : '—'}
					{:else if forecastStatus === 'error'}
						Wetter nicht verfügbar
					{:else}
						Wetterdaten werden geladen…
					{/if}
				</p>
			</div>
		</TopoBg>
	</GCard>
</div>
