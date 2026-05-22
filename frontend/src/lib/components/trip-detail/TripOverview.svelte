<script lang="ts">
	// Issue #302 — Trip-Detail Übersicht-Tab als 2×2 DetailCard-Grid.
	// Spec: docs/specs/modules/issue_302_trip_detail_page.md §5.
	//
	// Vier Karten: Reports, Alarmregeln, Route, Datenstand. Header-Infos (Hero,
	// Stats, Status) sind in TripHeader.svelte gewandert; FullProfile + StageList +
	// Right-Column-Previews leben jetzt in ihren jeweiligen Tabs.

	import type { Trip } from '$lib/types';
	import DetailCard, { type DetailCardItem } from './DetailCard.svelte';
	import { computeTripStats } from '$lib/utils/tripStats';
	import { getReportSchedule } from '$lib/utils/rightColumn';
	import { ALERT_METRIC_LABELS, SEVERITY_LABEL_DE, normalizeAlertMetric } from '$lib/utils/alertMetricLabels';

	interface Props {
		trip: Trip;
	}

	let { trip }: Props = $props();

	const stats = $derived(computeTripStats(trip));
	const schedule = $derived(getReportSchedule(trip));
	const enabledAlerts = $derived((trip.alert_rules ?? []).filter((r) => r.enabled));
	const waypointCount = $derived(
		(trip.stages ?? []).reduce((acc, s) => acc + (s.waypoints?.length ?? 0), 0)
	);

	const reportItems = $derived<DetailCardItem[]>([
		{
			label: 'Abend-Briefing',
			meta: schedule.evening ? `${schedule.evening} · E-Mail` : '—',
			state: schedule.enabled && !!schedule.evening ? 'on' : 'off'
		},
		{
			label: 'Morgen-Update',
			meta: schedule.morning ? `${schedule.morning} · E-Mail` : '—',
			state: schedule.enabled && !!schedule.morning ? 'on' : 'off'
		},
		{
			label: 'Warnungen',
			meta: `${enabledAlerts.length} Schwellen`,
			state: enabledAlerts.length > 0 ? 'on' : 'off'
		}
	]);

	function alertLabel(rule: typeof enabledAlerts[number]): string {
		const metricKey = normalizeAlertMetric(rule.metric);
		const meta = metricKey ? ALERT_METRIC_LABELS[metricKey] : undefined;
		if (!meta) return rule.metric;
		const cmp = meta.comparison;
		const unit = meta.unit ? ` ${meta.unit}` : '';
		return `${meta.label_de} ${cmp} ${rule.threshold}${unit}`;
	}

	const alertItems = $derived<DetailCardItem[]>(
		enabledAlerts.length === 0
			? [{ label: 'Keine Regel aktiv', state: 'off' as const }]
			: enabledAlerts.slice(0, 3).map((r) => ({
					label: alertLabel(r),
					meta: SEVERITY_LABEL_DE[r.severity],
					state: r.severity === 'critical' ? ('warn' as const) : ('on' as const)
				}))
	);

	const routeItems = $derived<DetailCardItem[]>([
		{ label: 'Gesamtdistanz', meta: `${stats.kmTotal.toFixed(1)} km` },
		{ label: 'Höhenmeter', meta: `↑${Math.round(stats.ascentM).toLocaleString('de-DE')} m` },
		{ label: 'Etappenanzahl', meta: `${stats.stages}` }
	]);

	const dataItems = $derived<DetailCardItem[]>([
		{ label: 'Wegpunkte', meta: `${waypointCount}` },
		{ label: 'Etappen', meta: `${stats.stages}` }
	]);
</script>

<section data-testid="trip-overview" class="trip-overview">
	<div class="overview-grid">
		<DetailCard
			testid="reports"
			eyebrow="REPORTS"
			title="Was geht raus"
			items={reportItems}
			actionText="Reports anpassen →"
			actionHref="#briefings"
		/>
		<DetailCard
			testid="alarmregeln"
			eyebrow={`ALARMREGELN · ${enabledAlerts.length}`}
			title="Wachhund-Schwellen"
			items={alertItems}
			actionText="Regeln verwalten →"
			actionHref="#alerts"
		/>
		<DetailCard
			testid="route"
			eyebrow={`${stats.stages} ETAPPEN`}
			title="Route & Etappen"
			items={routeItems}
			actionText="Etappen-Editor öffnen →"
			actionHref="#stages"
		/>
		<DetailCard
			testid="datenstand"
			eyebrow="LETZTER BRIEFING-LAUF"
			title="Datenstand"
			items={dataItems}
			actionText="Etappen →"
			actionHref="#stages"
		/>
	</div>
</section>

<style>
	.trip-overview {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}
	.overview-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1rem;
		padding: 1rem 0;
	}
	@media (max-width: 768px) {
		.overview-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
