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
		applyModeToRowState,
		ALL_ALERT_METRICS
	} from './alertMetricTable.ts';
	import AlertMetricRow from './AlertMetricRow.svelte';

	// Prop heisst `alert_rules` (Underscore), spiegelbildlich zu Trip.alert_rules
	// und konsistent mit AlertCooldownCard (cooldown_minutes) / AlertQuietHoursCard.
	// Issue #414: optionaler requestedMode steuert die abs/delta-Flags aller Zeilen.
	let { alert_rules = $bindable<AlertRule[]>([]), requestedMode }: { alert_rules: AlertRule[]; requestedMode?: 'absolute' | 'delta' | 'both' } = $props();

	// `existing` wird beim Mount eingefroren, damit IDs ueber spaetere
	// Row-State-Aenderungen hinweg stabil bleiben (Save-Pfad).
	const existing: AlertRule[] = [...(alert_rules ?? [])];
	let rowState = $state(alertRulesToRowState(alert_rules ?? [], existing));

	// Nach jeder Row-State-Aenderung: alert_rules zurueckschreiben.
	$effect(() => {
		alert_rules = rowStateToAlertRules(rowState, existing);
	});

	// Issue #414: Modus-Wechsel von aussen (AlertsTab-Picker) auf alle Zeilen anwenden.
	// F001: Erste $effect-Ausfuehrung (initial mount) ueberspringen, sonst wuerden
	// bestehende Trip-Konfigurationen beim blossen Oeffnen des Tabs ueberschrieben.
	let _hasModeApplied = false;
	$effect(() => {
		if (requestedMode !== undefined) {
			if (_hasModeApplied) {
				applyModeToRowState(rowState, requestedMode);
			} else {
				_hasModeApplied = true;
			}
		}
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
