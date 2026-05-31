<script lang="ts">
	// Issue #487 — TripOverview: 4-Karten-2×2-Dashboard (Design-Compliance).
	// Spec: docs/specs/modules/issue_487_trip_detail_overview_cards.md
	//
	// Ersetzt das bisherige zweispaltige Layout (Höhenprofil + Etappen-Liste +
	// rechte Preview-Karten aus Issue #409) durch ein kompaktes 2×2-Grid aus
	// 4 DetailCard-Kacheln. Jede Karte verlinkt in den vertiefenden Tab.

	import type { Trip, AlertRule } from '$lib/types';
	import DetailCard from './DetailCard.svelte';
	import type { DetailCardItem } from './DetailCard.svelte';
	import { getReportSchedule } from '$lib/utils/rightColumn';
	import { computeTripStats } from '$lib/utils/tripStats';
	import {
		normalizeAlertMetric,
		ALERT_METRIC_LABELS,
		thunderLevelLabel
	} from '$lib/utils/alertMetricLabels';

	interface Props {
		trip: Trip;
		now?: Date;
	}

	let { trip }: Props = $props();

	// Karte 1: Reports — „Was geht raus"
	const schedule = $derived(getReportSchedule(trip));
	const reportItems = $derived<readonly DetailCardItem[]>([
		{
			label: 'Abend-Briefing',
			meta:
				schedule.enabled && schedule.evening_enabled && schedule.evening
					? `täglich ${schedule.evening.slice(0, 5)} Uhr`
					: 'deaktiviert',
			state: schedule.enabled && schedule.evening_enabled ? 'on' : 'off'
		},
		{
			label: 'Morgen-Update',
			meta:
				schedule.enabled && schedule.morning_enabled && schedule.morning
					? `täglich ${schedule.morning.slice(0, 5)} Uhr`
					: 'deaktiviert',
			state: schedule.enabled && schedule.morning_enabled ? 'on' : 'off'
		},
		{
			label: 'Alerts bei Änderungen',
			meta: schedule.alertOnChanges ? 'aktiv' : 'deaktiviert',
			state: schedule.alertOnChanges ? 'on' : 'off'
		}
	]);

	// Karte 2: Alert Rules — „Wachhund-Schwellen"
	const enabledRules = $derived((trip.alert_rules ?? []).filter((r) => r.enabled).slice(0, 4));
	const alertCount = $derived(enabledRules.length);

	function alertLabel(rule: AlertRule): string {
		const key = normalizeAlertMetric(rule.metric);
		const meta = key ? ALERT_METRIC_LABELS[key] : undefined;
		if (!meta) return rule.metric;
		if (key === 'thunder_level') return `Gewitter ${thunderLevelLabel(rule.threshold)}`;
		const unit = meta.unit ? ` ${meta.unit}` : '';
		return `${meta.label_de} ${meta.comparison} ${rule.threshold}${unit}`;
	}

	const alertItems = $derived<readonly DetailCardItem[]>(
		enabledRules.length === 0
			? [{ label: 'Noch keine Regeln', state: 'off' }]
			: enabledRules.map((r) => ({ label: alertLabel(r), state: 'on' as const }))
	);

	// Karte 3: Route & Etappen
	const stats = $derived(computeTripStats(trip));
	const stageItems = $derived<readonly DetailCardItem[]>(
		stats.stages === 0
			? [
					{ label: 'Distanz', meta: '—', state: 'off' },
					{ label: 'Aufstieg', meta: '—', state: 'off' },
					{ label: 'Etappen', meta: '—', state: 'off' }
				]
			: [
					{ label: 'Distanz', meta: `${stats.kmTotal.toFixed(1)} km`, state: 'on' },
					{
						label: 'Aufstieg',
						meta: `${Math.round(stats.ascentM).toLocaleString('de-DE')} m`,
						state: 'on'
					},
					{ label: 'Etappen', meta: `${stats.stages} geplant`, state: 'on' }
				]
	);

	// Karte 4: Datenstand
	const nextBriefing = $derived(
		(() => {
			if (!schedule.enabled) return '—';
			const times = [
				schedule.morning_enabled && schedule.morning ? schedule.morning.slice(0, 5) : null,
				schedule.evening_enabled && schedule.evening ? schedule.evening.slice(0, 5) : null
			]
				.filter((t): t is string => t !== null)
				.sort();
			return times[0] ?? '—';
		})()
	);

	const zeitplanLabel = $derived(
		schedule.morning_enabled && schedule.evening_enabled
			? '2× täglich'
			: schedule.morning_enabled
				? 'Morgens'
				: schedule.evening_enabled
					? 'Abends'
					: 'inaktiv'
	);

	const scheduleItems = $derived<readonly DetailCardItem[]>([
		{
			label: 'Nächstes Briefing',
			meta: nextBriefing,
			state: schedule.enabled ? 'on' : 'off'
		},
		{
			label: 'Zeitplan',
			meta: zeitplanLabel,
			state: schedule.enabled ? 'on' : 'off'
		},
		{
			label: 'Warnungen',
			meta: `${alertCount} Regeln aktiv`,
			state: alertCount > 0 ? 'on' : 'off'
		}
	]);
</script>

<section data-testid="trip-overview" class="trip-overview">
	<div class="overview-grid">
		<DetailCard
			eyebrow="Reports"
			title="Was geht raus"
			items={reportItems}
			actionText="Reports & Kanäle"
			actionHref="#briefings"
			testid="card-reports"
		/>
		<DetailCard
			eyebrow="{alertCount} Alarmregeln"
			title="Wachhund-Schwellen"
			items={alertItems}
			actionText="Alarmregeln verwalten"
			actionHref="#alerts"
			testid="card-alerts"
		/>
		<DetailCard
			eyebrow="{stats.stages} Etappen"
			title="Route & Etappen"
			items={stageItems}
			actionText="Etappen öffnen"
			actionHref="#stages"
			testid="card-stages"
		/>
		<DetailCard
			eyebrow="Briefings"
			title="Datenstand"
			items={scheduleItems}
			actionText="Briefing-Vorschau"
			actionHref="#preview"
			testid="card-schedule"
		/>
	</div>
</section>

<style>
	.trip-overview {
		padding-top: var(--g-s-4, 1.5rem);
	}
	.overview-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--g-s-4, 1.5rem);
	}
	@media (max-width: 899px) {
		.overview-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
