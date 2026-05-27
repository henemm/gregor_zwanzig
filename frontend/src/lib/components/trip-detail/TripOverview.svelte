<script lang="ts">
	// Issue #409 — Trip-Detail Übersicht-Tab: Höhenprofil + Etappen-Layout
	// statt Card-Grid.
	// Spec: docs/specs/modules/issue_409_trip_detail_overview.md

	import type { Trip } from '$lib/types';
	import FullProfile from './FullProfile.svelte';
	import StageList from './StageList.svelte';
	import BriefingPreviewCard from './BriefingPreviewCard.svelte';
	import WeatherMetricsPreviewCard from './WeatherMetricsPreviewCard.svelte';
	import AlertsPreviewCard from './AlertsPreviewCard.svelte';
	import PreviewCard from './PreviewCard.svelte';
	import Stat from '$lib/components/molecules/Stat.svelte';
	import { computeTripStats } from '$lib/utils/tripStats';
	import { getReportSchedule } from '$lib/utils/rightColumn';
	import { getActiveStageId } from '$lib/utils/fullProfile';
	import { deriveTripStatus } from '$lib/utils/tripStatus';

	interface Props {
		trip: Trip;
		now?: Date;
	}

	let { trip, now = new Date() }: Props = $props();

	let selectedStageId = $state<string | null>(null);

	const stats = $derived(computeTripStats(trip));
	const schedule = $derived(getReportSchedule(trip));
	const status = $derived(deriveTripStatus(trip, now));
	const activeId = $derived(getActiveStageId(trip, now));
	const stages = $derived(trip.stages ?? []);

	// Etappen-Kachel: "aktiveIndex+1 / Gesamt" oder "– / Gesamt"
	const activeIndex = $derived(
		activeId !== null ? stages.findIndex((s) => s.id === activeId) : -1
	);
	const etappeValue = $derived(
		activeIndex >= 0 ? `${activeIndex + 1}/${stats.stages}` : `–/${stats.stages}`
	);

	// Briefing-Kachel: früheste aktivierte Zeit
	const briefingTimes = $derived(
		(
			[
				schedule.enabled && schedule.morning_enabled && schedule.morning
					? schedule.morning
					: null,
				schedule.enabled && schedule.evening_enabled && schedule.evening
					? schedule.evening
					: null
			].filter(Boolean) as string[]
		).sort()
	);
	const nextBriefing = $derived(briefingTimes[0] ?? '–:–');

	// Start-Kachel: Tage bis ersten Stage-Datum
	const startStage = $derived(stages.find((s) => !!s.date));
	const daysValue = $derived(
		(() => {
			if (status === 'active') return 'Läuft';
			if (!startStage?.date) return '–';
			const todayMs = new Date(now.toISOString().slice(0, 10) + 'T00:00:00Z').getTime();
			const startMs = new Date(startStage.date.slice(0, 10) + 'T00:00:00Z').getTime();
			const diff = Math.ceil((startMs - todayMs) / 86_400_000);
			return diff === 0 ? 'Heute' : `${diff} Tg`;
		})()
	);
	const daysLabel = $derived(status === 'active' ? 'STATUS' : 'START IN');

	function handleSelectStage(id: string): void {
		selectedStageId = id;
	}
</script>

<section data-testid="trip-overview" class="trip-overview">
	<div data-testid="trip-hero" class="trip-hero">
		<div data-testid="trip-hero-title" class="trip-hero-title">{trip.name}</div>
		<div class="hero-stats">
			<div data-testid="trip-hero-stat-active-stage">
				<Stat label="ETAPPE" value={etappeValue} size="sm" mono />
			</div>
			<div data-testid="trip-hero-stat-next-briefing">
				<Stat label="BRIEFING" value={nextBriefing} size="sm" mono />
			</div>
			<div data-testid="trip-hero-stat-days">
				<Stat label={daysLabel} value={daysValue} size="sm" mono />
			</div>
		</div>
	</div>

	<div class="overview-columns">
		<div data-testid="trip-overview-left-column" class="left-column">
			<FullProfile {trip} {selectedStageId} onSelectStage={handleSelectStage} {now} />
			<StageList {trip} {selectedStageId} onSelectStage={handleSelectStage} {now} />
		</div>

		<aside data-testid="trip-overview-right-column" class="right-column">
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
		gap: var(--g-s-4, 1.5rem);
	}

	.trip-hero {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-2, 0.5rem);
	}

	.trip-hero-title {
		font-size: var(--g-text-lg, 1.125rem);
		font-weight: 600;
		color: var(--g-ink);
	}

	.hero-stats {
		display: flex;
		gap: var(--g-s-4, 1.5rem);
		flex-wrap: wrap;
	}

	.overview-columns {
		display: grid;
		grid-template-columns: 2fr 1fr;
		gap: var(--g-s-4, 1.5rem);
		align-items: start;
	}

	.left-column {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-4, 1.5rem);
	}

	.right-column {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-3, 1rem);
	}

	@media (max-width: 899px) {
		.overview-columns {
			grid-template-columns: 1fr;
		}
	}
</style>
