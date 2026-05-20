<script lang="ts">
	// Issue #180 — Tabelle aller AlertMetric-Zeilen.
	// Spec: docs/specs/modules/issue_180_alert_metric_table.md §AlertMetricTable.svelte.
	//
	// Initialisiert Row-State aus `alertRules` und reicht jede Zeile in eine
	// AlertMetricRow weiter. $effect spiegelt Row-State-Aenderungen zurueck nach
	// `alertRules` (bind aufwaerts an AlertsTab).

	import type { AlertRule } from '$lib/types';
	import {
		alertRulesToRowState,
		rowStateToAlertRules,
		ALL_ALERT_METRICS
	} from './alertMetricTable.ts';
	import AlertMetricRow from './AlertMetricRow.svelte';

	// Prop heisst `alert_rules` (Underscore), spiegelbildlich zu Trip.alert_rules
	// und konsistent mit AlertCooldownCard (cooldown_minutes) / AlertQuietHoursCard.
	let { alert_rules = $bindable<AlertRule[]>([]) }: { alert_rules: AlertRule[] } = $props();

	// `existing` wird beim Mount eingefroren, damit IDs ueber spaetere
	// Row-State-Aenderungen hinweg stabil bleiben (Save-Pfad).
	const existing: AlertRule[] = [...(alert_rules ?? [])];
	let rowState = $state(alertRulesToRowState(alert_rules ?? [], existing));

	// Nach jeder Row-State-Aenderung: alert_rules zurueckschreiben.
	$effect(() => {
		alert_rules = rowStateToAlertRules(rowState, existing);
	});
</script>

<div class="alert-metric-table" data-testid="alert-metric-table">
	{#each ALL_ALERT_METRICS as m (m)}
		<AlertMetricRow metric={m} bind:state={rowState[m]} />
	{/each}
</div>

<style>
	.alert-metric-table {
		display: flex;
		flex-direction: column;
		border: 1px solid var(--g-ink-faint);
		border-radius: 0.5rem;
		background: var(--g-surface-1, #fff);
	}
</style>
