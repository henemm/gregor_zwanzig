<script lang="ts">
	// Epic #135 Step 4 — Trip-Overview-Wrapper (Hero + 2-Spalten-Grid).
	// Spec: docs/specs/modules/epic_135_step4_left_column.md §2.
	//
	// Kapselt Hero (Step 3) + linke Spalte (FullProfile + StageList) +
	// rechte Spalte (Platzhalter fuer #158 + #159). `selectedStageId` lebt
	// hier zentral und wird sowohl an FullProfile als auch StageList weitergegeben,
	// damit Klicks in beiden Komponenten den gleichen State teilen (AC-10).

	import type { Trip } from '$lib/types';
	import TripHero from './TripHero.svelte';
	import FullProfile from './FullProfile.svelte';
	import StageList from './StageList.svelte';
	import BriefingPreviewCard from './BriefingPreviewCard.svelte';
	import WeatherMetricsPreviewCard from './WeatherMetricsPreviewCard.svelte';
	import AlertsPreviewCard from './AlertsPreviewCard.svelte';
	import PreviewCard from './PreviewCard.svelte';

	interface Props {
		trip: Trip;
		now?: Date;
	}

	let { trip, now = new Date() }: Props = $props();

	let selectedStageId = $state<string | null>(null);

	function handleSelectStage(id: string) {
		selectedStageId = id;
	}
</script>

<section data-testid="trip-overview" class="trip-overview">
	<TripHero {trip} {now} />

	<div class="trip-overview-grid">
		<div data-testid="trip-overview-left-column" class="trip-overview-left">
			<FullProfile
				{trip}
				{selectedStageId}
				onSelectStage={handleSelectStage}
				{now}
			/>
			<StageList
				{trip}
				{selectedStageId}
				onSelectStage={handleSelectStage}
				{now}
			/>
		</div>

		<aside data-testid="trip-overview-right-column" class="trip-overview-right">
			<BriefingPreviewCard {trip} />
			<WeatherMetricsPreviewCard {trip} />
			<AlertsPreviewCard {trip} />
			<PreviewCard {trip} />
		</aside>
	</div>
</section>

<style>
	.trip-overview {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}
	.trip-overview-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 1.5rem;
	}
	@media (min-width: 1024px) {
		.trip-overview-grid {
			grid-template-columns: 2fr 1fr;
		}
	}
	.trip-overview-left {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}
	.trip-overview-right {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		min-height: 1px;
	}
</style>
