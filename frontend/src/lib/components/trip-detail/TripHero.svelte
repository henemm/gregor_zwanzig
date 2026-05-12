<script lang="ts">
	// Spec: docs/specs/modules/epic_135_step3_trip_hero.md
	// Trip-Hero im Overview-Tab: H1 + optionale Zeitraum-Zeile + 3 Stat-Kacheln.
	// Reagiert reaktiv auf trip-Mutationen (Status-Updates aus Step 2) via $derived.
	import type { Trip } from '$lib/types';
	import {
		formatDateRange,
		getActiveStageDisplay,
		getNextBriefing,
		getDaysLabel
	} from '$lib/utils/tripHero';

	interface Props {
		trip: Trip;
		now?: Date;
	}

	let { trip, now = new Date() }: Props = $props();

	const dateRange = $derived(formatDateRange(trip));
	const activeStageText = $derived(getActiveStageDisplay(trip, now));
	const nextBriefingText = $derived(getNextBriefing(trip, now));
	const daysText = $derived(getDaysLabel(trip, now));
</script>

{#snippet statTile(label: string, value: string, testid: string)}
	<div data-testid={testid} class="stat-tile">
		<span class="eyebrow">{label}</span>
		<span class="stat-value">{value}</span>
	</div>
{/snippet}

<div data-testid="trip-hero" class="trip-hero">
	<h1 data-testid="trip-hero-title" class="trip-hero-title">{trip.name}</h1>
	{#if dateRange}
		<p data-testid="trip-hero-date-range" class="trip-hero-date-range">{dateRange}</p>
	{/if}
	<div class="grid grid-cols-1 sm:grid-cols-3 gap-4 trip-hero-stats">
		{@render statTile('Aktive Etappe', activeStageText, 'trip-hero-stat-active-stage')}
		{@render statTile('Nächstes Briefing', nextBriefingText, 'trip-hero-stat-next-briefing')}
		{@render statTile('Tage bis Start', daysText, 'trip-hero-stat-days')}
	</div>
</div>

<style>
	.trip-hero {
		padding: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.trip-hero-title {
		font-size: 1.5rem;
		font-weight: 700;
		line-height: 1.2;
	}
	.trip-hero-date-range {
		font-size: 0.875rem;
		color: var(--g-ink-faint, #6b7280);
	}
	.trip-hero-stats {
		margin-top: 0.5rem;
	}
	.stat-tile {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding: 0.75rem 1rem;
		border-radius: 0.5rem;
		background: var(--g-surface-2, rgba(0, 0, 0, 0.03));
	}
	.eyebrow {
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 0.6875rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--g-ink-faint, #6b7280);
	}
	.stat-value {
		font-size: 1rem;
		font-weight: 600;
		color: var(--g-ink, inherit);
	}
</style>
