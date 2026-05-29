<script lang="ts">
	// Issue #302 — Trip-Detail Header (Soll-Mockup).
	// Spec: docs/specs/modules/issue_302_trip_detail_page.md §3.
	//
	// Zweispaltig: Links Breadcrumb + H1 + Statuszeile + Meta. Rechts 3 Buttons.
	// Pause/Archive-Logik ist in +page.svelte als Danger-Zone gewandert.
	import { Btn } from '$lib/components/ui/btn/index.js';
	import { Eyebrow } from '$lib/components/ui/eyebrow';
	import TripStatusBadge from './TripStatusBadge.svelte';
	import { formatDateRange, getDaysLabel } from '$lib/utils/tripHero';
	import { computeTripStats } from '$lib/utils/tripStats';
	import { deriveTripStatus, todayStageIndex } from '$lib/utils/tripStatus';
	import { getReportSchedule } from '$lib/utils/rightColumn';
	import Stat from '$lib/components/molecules/Stat.svelte';
	import { api } from '$lib/api';
	import { goto } from '$app/navigation';
	import type { Trip } from '$lib/types';

	interface Props {
		trip: Trip;
		// onStatusChange ist obsolet — Pause/Archive haben die Komponente verlassen.
		// Prop bleibt zur Backward-Compatibility, wird nicht mehr ausgelöst.
		onStatusChange?: (updated: Trip) => void;
		now?: Date;
	}

	let { trip, now = new Date() }: Props = $props();

	const stats = $derived(computeTripStats(trip));
	const dateRange = $derived(formatDateRange(trip));
	const daysLabel = $derived(getDaysLabel(trip, now));

	// Issue #416 — Mobile Kennzahlen-Kacheln (sichtbar nur ≤ 899px).
	// Spec: docs/specs/modules/issue_416_mobile_trip_kennzahlen.md
	const etappeValue = $derived((() => {
		const total = trip.stages?.length ?? 0;
		if (total === 0) return '—';
		const s = deriveTripStatus(trip, now);
		if (s === 'active') {
			const idx = todayStageIndex(trip, now);
			return idx >= 0 ? `${idx + 1}/${total}` : `—/${total}`;
		}
		if (s === 'archived') return `${total}/${total}`;
		return `—/${total}`;
	})());

	const briefingValue = $derived((() => {
		const sched = getReportSchedule(trip);
		if (!sched.enabled) return '—';
		if (sched.morning_enabled && sched.morning) return sched.morning.slice(0, 5);
		if (sched.evening_enabled && sched.evening) return sched.evening.slice(0, 5);
		return '—';
	})());

	const startLabel = $derived((() => {
		const s = deriveTripStatus(trip, now);
		if (s === 'planned') return 'START IN';
		if (s === 'active') return 'TAG';
		return 'STATUS';
	})());

	const startValue = $derived((() => {
		const s = deriveTripStatus(trip, now);
		if (s === 'planned') {
			const dates = (trip.stages ?? [])
				.map((st) => st.date)
				.filter((d): d is string => !!d)
				.sort();
			if (!dates.length) return '—';
			const firstDay = new Date(dates[0] + 'T00:00:00');
			const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
			const diff = Math.ceil((firstDay.getTime() - today.getTime()) / 86_400_000);
			return diff > 0 ? `${diff} Tg` : '—';
		}
		if (s === 'active') {
			const idx = todayStageIndex(trip, now);
			return idx >= 0 ? `Tag ${idx + 1}` : '—';
		}
		return '—';
	})());

	let testBriefingLoading = $state(false);
	let testBriefingMsg = $state<string | null>(null);

	async function handleTestBriefing(): Promise<void> {
		testBriefingLoading = true;
		testBriefingMsg = null;
		try {
			await api.post('/api/scheduler/trip-reports?hour=18', {});
			testBriefingMsg = 'Briefings für alle aktiven Trips ausgelöst.';
		} catch {
			testBriefingMsg = 'Fehler beim Senden.';
		} finally {
			testBriefingLoading = false;
		}
	}

	function handlePreview(): void {
		void goto(`/trips/${trip.id}#preview`);
	}

	function handleEdit(): void {
		void goto(`/trips/${trip.id}/edit`);
	}
</script>

<header class="trip-header">
	<div class="header-main">
		<div class="header-left">
			<nav data-testid="trip-detail-breadcrumb" aria-label="Breadcrumb" class="breadcrumb">
				<Eyebrow>
					<a href="/trips" data-testid="trip-detail-breadcrumb-link-trips">MEINE TRIPS</a>
					<span aria-hidden="true"> › </span>
					<span data-testid="trip-detail-breadcrumb-current">
						{(trip.shortcode ?? trip.name).toUpperCase()}
					</span>
				</Eyebrow>
			</nav>

			<h1 class="trip-h1" data-testid="trip-detail-h1">
				{#if trip.shortcode}<span class="h1-shortcode">{trip.shortcode}</span> ·&nbsp;{/if}{trip.name}
			</h1>

			<div class="status-line">
				<span class="status-supplement" data-testid="trip-detail-status-supplement">
					{daysLabel}
				</span>
				<TripStatusBadge {trip} {now} />
			</div>

			<div class="meta-line" data-testid="trip-detail-meta">
				{#if dateRange}<span>{dateRange}</span> · {/if}<span>{stats.kmTotal.toFixed(1)} km</span>
				· <span>↑{Math.round(stats.ascentM).toLocaleString('de-DE')} m</span>
			</div>
		</div>

		<div class="header-actions">
			<Btn
				variant="outline"
				size="sm"
				data-testid="trip-detail-action-preview"
				onclick={handlePreview}
			>
				Briefing-Vorschau
			</Btn>
			<Btn
				variant="outline"
				size="sm"
				data-testid="trip-detail-action-edit"
				onclick={handleEdit}
			>
				Bearbeiten
			</Btn>
			<Btn
				variant="accent"
				size="sm"
				data-testid="trip-detail-action-test-briefing"
				onclick={handleTestBriefing}
				disabled={testBriefingLoading}
			>
				Test-Briefing senden
			</Btn>
		</div>
	</div>

	<div class="mobile-metrics" data-testid="trip-header-mobile-metrics">
		<div data-testid="metric-etappe">
			<Stat label="ETAPPE" value={etappeValue} size="sm" mono />
		</div>
		<div data-testid="metric-briefing">
			<Stat label="BRIEFING" value={briefingValue} size="sm" mono />
		</div>
		<div data-testid="metric-start">
			<Stat label={startLabel} value={startValue} size="sm" mono />
		</div>
	</div>

	{#if testBriefingMsg}
		<p class="briefing-msg" data-testid="trip-detail-test-briefing-msg">{testBriefingMsg}</p>
	{/if}
</header>

<style>
	.trip-header {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-bottom: 1.25rem;
	}
	.header-main {
		display: flex;
		gap: 1.5rem;
		align-items: flex-start;
		justify-content: space-between;
		flex-wrap: wrap;
	}
	.header-left {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		min-width: 0;
		flex: 1 1 320px;
	}
	.breadcrumb a {
		color: inherit;
		text-decoration: none;
	}
	.breadcrumb a:hover {
		text-decoration: underline;
	}
	.trip-h1 {
		margin: 0;
		font-size: var(--g-text-3xl);
		font-weight: 700;
		letter-spacing: -0.025em;
		color: var(--g-ink);
		line-height: 1.15;
	}
	.h1-shortcode {
		font-family: var(--g-font-mono, ui-monospace, monospace);
		color: var(--g-accent); /* audit:exempt — Large-Text in <h1> (≥18pt → WCAG AA-large) */
	}
	.status-line {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
	}
	.status-supplement {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
	}
	.meta-line {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem;
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		font-variant-numeric: tabular-nums;
	}
	.header-actions {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		flex-shrink: 0;
	}
	.briefing-msg {
		margin: 0;
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
	}
	.mobile-metrics {
		display: none;
	}
	@media (max-width: 899px) {
		.mobile-metrics {
			display: flex;
			gap: var(--g-s-3);
			padding-top: var(--g-s-2);
		}
	}
</style>
