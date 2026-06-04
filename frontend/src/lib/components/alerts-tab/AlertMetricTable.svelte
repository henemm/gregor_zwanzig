<script lang="ts">
	// Issue #180 — Tabelle aller AlertMetric-Zeilen.
	// Spec: docs/specs/modules/issue_180_alert_metric_table.md §AlertMetricTable.svelte.
	// Issue #586 — Card-Wrapper + Header-Row nach JSX.

	import type { AlertRule } from '$lib/types';
	import {
		alertRulesToRowState,
		rowStateToAlertRules,
		applyModeToRowState,
		ALL_ALERT_METRICS
	} from './alertMetricTable.ts';
	import AlertMetricRow from './AlertMetricRow.svelte';
	import { Card, Eyebrow } from '$lib/components/atoms';

	let { alert_rules = $bindable<AlertRule[]>([]), requestedMode }: { alert_rules: AlertRule[]; requestedMode?: 'absolute' | 'delta' | 'both' } = $props();

	const existing: AlertRule[] = [...(alert_rules ?? [])];
	let rowState = $state(alertRulesToRowState(alert_rules ?? [], existing));

	$effect(() => {
		alert_rules = rowStateToAlertRules(rowState, existing);
	});

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

<Card padding={0}>
	<div class="table-header">
		<div></div>
		<Eyebrow>Metrik</Eyebrow>
		<Eyebrow>Δ-Änderung (seit letztem Briefing)</Eyebrow>
		<Eyebrow>Absoluter Schwellwert</Eyebrow>
		<div></div>
	</div>
	<div class="alert-metric-table" data-testid="alert-metric-table">
		{#each ALL_ALERT_METRICS as m (m)}
			<AlertMetricRow metric={m} bind:state={rowState[m]} />
		{/each}
	</div>
</Card>

<style>
	.table-header {
		display: grid;
		grid-template-columns: 32px 200px 1fr 1fr auto;
		gap: 0;
		padding: 12px 20px;
		background: var(--g-card-alt);
		border-bottom: 1px solid var(--g-rule);
		align-items: center;
	}
	.alert-metric-table {
		display: flex;
		flex-direction: column;
	}
</style>
