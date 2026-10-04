<script lang="ts">
	// Issue #302 — Trip-Detail Header (Soll-Mockup).
	// Spec: docs/specs/modules/issue_302_trip_detail_page.md §3.
	//
	// Zweispaltig: Links Breadcrumb + H1 + Statuszeile + Meta. Rechts 3 Buttons.
	// Pause/Archive-Logik ist in +page.svelte als Danger-Zone gewandert.
	import TripStatusBadge from './TripStatusBadge.svelte';
	import { api } from '$lib/api.js';
	import { formatDateRange, getDaysLabel } from '$lib/utils/tripHero';
	import { computeTripStats } from '$lib/utils/tripStats';
	import { deriveTripStatus, todayStageIndex } from '$lib/utils/tripStatus';
	import { getReportSchedule } from '$lib/utils/rightColumn';
	import Stat from '$lib/components/molecules/Stat.svelte';
	import { ACTIVITY_TYPE_OPTIONS, type Trip } from '$lib/types';
	import SubscriptionHeader from '$lib/components/shared/subscription-header/SubscriptionHeader.svelte';
	import { baueTripSpeicherung, speichereOderMeldeKonflikt } from '$lib/components/shared/tripSpeicherung';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';

	interface Props {
		trip: Trip;
		// onStatusChange ist obsolet — Pause/Archive haben die Komponente verlassen.
		// Prop bleibt zur Backward-Compatibility, wird nicht mehr ausgelöst.
		onStatusChange?: (updated: Trip) => void;
		onTripUpdate?: (updated: Trip) => void;
		now?: Date;
		/** Issue #758: SaveStatus controller — der Speicher-Chip kommt seit #2284 S2 vom SubscriptionHeader. */
		saveController?: SaveStatus;
	}

	let { trip, onTripUpdate, now = new Date(), saveController }: Props = $props();

	// Issue #2284 S2 — Name, Region und Aktivität speichert der geteilte Baustein
	// über diese Funktion. Rumpf = NUR das Eigenfeld (kein Spread des Seiten-Trips,
	// Fehlerklasse #2375/#2381); Schlüssel je Feld, damit ein 412-Konflikt je Feld
	// genau einen „Nochmal speichern"-Eintrag hat (#1433). Ausgänge: Erfolg ⇒
	// onTripUpdate + schliessen; 412 ⇒ erfüllt ohne schliessen (Retry schließt);
	// sonst wirft es und der Baustein zeigt die Meldung.
	async function onSaveField(field: 'name' | 'region' | 'profile', value: string, schliessen: () => void): Promise<void> {
		const rumpf = field === 'name' ? { name: value } : field === 'region' ? { region: value } : { activity: value };
		const schluessel = field === 'name' ? 'kopf-name' : field === 'region' ? 'kopf-region' : 'kopf-profil';
		const speichern = baueTripSpeicherung<Trip>(api, trip.id, rumpf, (updated) => {
			onTripUpdate?.(updated);
			schliessen();
		}, schluessel);
		await speichereOderMeldeKonflikt(speichern, saveController);
	}

	const stats = $derived(computeTripStats(trip));
	const dateRange = $derived(formatDateRange(trip));

	// Issue #2284 S2 — Eyebrow zeigt nur noch den Datumsbereich; die Region steht in der Region-Zeile des Bausteins.
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
		if (s === 'archived' || s === 'finished') return `${total}/${total}`;
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


</script>

<header class="trip-header">
	<div class="header-main">
		<div class="header-left">
			<SubscriptionHeader
				kind="trip"
				name={trip.name}
				region={trip.region}
				profile={trip.activity}
				profileOptions={ACTIVITY_TYPE_OPTIONS}
				regionMaxLength={60}
				testidPrefix="trip"
				titleTestid="trip-detail-h1"
				{saveController}
				{onSaveField}
			>
				{#snippet eyebrow()}
					<div class="trip-eyebrow-region">{dateRange}</div>
				{/snippet}
				{#snippet namePrefix()}
					{#if trip.shortcode}<span class="h1-shortcode">{trip.shortcode}</span> ·&nbsp;{/if}
				{/snippet}
			</SubscriptionHeader>

			<div class="status-line">
				<span class="status-supplement" data-testid="trip-detail-status-supplement">
					{daysLabel}
				</span>
				<TripStatusBadge {trip} {now} />
			</div>

			<div class="meta-line" data-testid="trip-detail-meta">
				<span>{stats.kmTotal.toFixed(1)} km</span>
				· <span>↑{Math.round(stats.ascentM).toLocaleString('de-DE')} m</span>
			</div>
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
</header>

<style>
	.trip-header {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-bottom: 1.25rem;
		padding: 26px 40px 18px;
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
	}
	.trip-eyebrow-region {
		font-size: 11px;
		font-family: var(--g-font-mono, ui-monospace, monospace);
		color: var(--g-ink-3);
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}
	/* Mobile Usability Paket 1 (F1, PO 2026-09-22): Titel auf Mobile via
	   Token-Skala, einzeilig mit Ellipsis — kein Überstehen bei langen Namen. */
	@media (max-width: 899px) {
		.trip-h1-row {
			flex-wrap: nowrap;
			min-width: 0;
		}
		.trip-h1 {
			font-size: var(--g-text-xl);
			min-width: 0;
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
		}
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
