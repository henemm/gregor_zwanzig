<script lang="ts">
	// Issue #302 — Trip-Detail Header (Soll-Mockup).
	// Spec: docs/specs/modules/issue_302_trip_detail_page.md §3.
	//
	// Zweispaltig: Links Breadcrumb + H1 + Statuszeile + Meta. Rechts 3 Buttons.
	// Pause/Archive-Logik ist in +page.svelte als Danger-Zone gewandert.
	import { Btn } from '$lib/components/atoms';
	import TripStatusBadge from './TripStatusBadge.svelte';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import { api } from '$lib/api.js';
	import { formatDateRange, getDaysLabel } from '$lib/utils/tripHero';
	import { computeTripStats } from '$lib/utils/tripStats';
	import { deriveTripStatus, todayStageIndex } from '$lib/utils/tripStatus';
	import { getReportSchedule } from '$lib/utils/rightColumn';
	import Stat from '$lib/components/molecules/Stat.svelte';
	import type { Trip } from '$lib/types';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import SaveIndicator from '$lib/components/ui/SaveIndicator.svelte';

	interface Props {
		trip: Trip;
		// onStatusChange ist obsolet — Pause/Archive haben die Komponente verlassen.
		// Prop bleibt zur Backward-Compatibility, wird nicht mehr ausgelöst.
		onStatusChange?: (updated: Trip) => void;
		onTripUpdate?: (updated: Trip) => void;
		now?: Date;
		/** Issue #758: SaveStatus controller — rendert SaveIndicator in der Header-Zeile. */
		saveController?: SaveStatus;
	}

	let { trip, onTripUpdate, now = new Date(), saveController }: Props = $props();

	// AC-6 — Inline Trip-Name-Bearbeitung (kein separater /edit-Screen mehr)
	// #713 — toggle: nur via Stift-Icon editierbar (kein dauerhaftes Eingabefeld)
	let editName = $state(trip.name);
	let nameSaving = $state(false);
	let isEditingName = $state(false);
	let nameSaveError: string | null = $state(null);

	function makeNameSaveHandler() {
		return async function doNameSave() {
			nameSaving = true;
			nameSaveError = null;
			try {
				await api.put(`/api/trips/${trip.id}`, { name: editName });
				onTripUpdate?.({ ...trip, name: editName });
				isEditingName = false;
			} catch (e: unknown) {
				nameSaveError = (e as { error?: string })?.error || 'Speichern fehlgeschlagen';
			} finally {
				nameSaving = false;
			}
		};
	}

	const stats = $derived(computeTripStats(trip));
	const dateRange = $derived(formatDateRange(trip));

	// Issue #699 — Eyebrow im Format "REGION · DATUMSBEREICH". Fehlt eine
	// Komponente, bleibt nur die vorhandene ohne verwaistes "·"-Trennzeichen.
	const eyebrowText = $derived([trip.region, dateRange].filter(Boolean).join(' · '));
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


</script>

<header class="trip-header">
	<div class="header-main">
		<div class="header-left">
			<div class="trip-eyebrow-region">
				{eyebrowText}
			</div>

			<div class="trip-h1-row">
				<h1 class="trip-h1" data-testid="trip-detail-h1">
					{#if trip.shortcode}<span class="h1-shortcode">{trip.shortcode}</span> ·&nbsp;{/if}{trip.name}
				</h1>
				{#if !isEditingName}
					<button
						type="button"
						class="name-edit-toggle"
						data-testid="trip-name-edit-toggle"
						aria-label="Trip-Name bearbeiten"
						onclick={() => { editName = trip.name; nameSaveError = null; isEditingName = true; }}
					>
						<PencilIcon size={15} />
					</button>
				{/if}
			</div>

			{#if isEditingName}
			<div class="name-edit-row">
				<input
					type="text"
					data-testid="trip-name-edit"
					class="name-edit-input"
					bind:value={editName}
					aria-label="Trip-Name bearbeiten"
				/>
				<Btn
					variant="ghost"
					size="sm"
					data-testid="trip-name-save"
					disabled={nameSaving}
					onclick={makeNameSaveHandler()}
				>{nameSaving ? '…' : 'Umbenennen'}</Btn>
				<Btn
					variant="ghost"
					size="sm"
					onclick={() => { editName = trip.name; nameSaveError = null; isEditingName = false; }}
				>Abbrechen</Btn>
			</div>
			{#if nameSaveError}<div class="name-edit-error" data-testid="trip-name-save-error" role="alert">{nameSaveError}</div>{/if}
			{/if}

			<div class="status-line">
				<span class="status-supplement" data-testid="trip-detail-status-supplement">
					{daysLabel}
				</span>
				<TripStatusBadge {trip} {now} />
				{#if saveController}
					<SaveIndicator controller={saveController} />
				{/if}
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
	.trip-h1 {
		margin: 0;
		font-size: 38px;
		font-weight: 700;
		letter-spacing: -0.02em;
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
	}
	.trip-eyebrow-region {
		font-size: 11px;
		font-family: var(--g-font-mono, ui-monospace, monospace);
		color: var(--g-ink-3);
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}
	.trip-h1-row {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
	}
	.name-edit-toggle {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		background: transparent;
		border: none;
		cursor: pointer;
		color: var(--g-ink-3);
		padding: 4px;
		border-radius: var(--g-r-1);
		flex-shrink: 0;
	}
	.name-edit-toggle:hover {
		color: var(--g-ink);
		background: var(--g-paper-deep);
	}
	.name-edit-row {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-top: 2px;
	}
	.name-edit-input {
		flex: 1 1 auto;
		max-width: 380px;
		font-size: var(--g-text-sm);
		color: var(--g-ink);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-1, 0.375rem);
		background: var(--g-card, #fff);
		padding: 4px 8px;
		outline: none;
	}
	.name-edit-input:focus {
		border-color: var(--g-accent);
	}
	.name-edit-error {
		font-size: var(--g-text-sm);
		color: var(--g-danger);
		margin-top: 2px;
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
