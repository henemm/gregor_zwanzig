<script lang="ts">
	// Issue #180 — Eine Zeile der Schwellwert-Tabelle.
	// Spec: docs/specs/modules/issue_180_alert_metric_table.md §AlertMetricRow.svelte.
	//
	// Layout je Zeile (Standard-Metrik):
	//   [Label]  [Abs-Toggle] [Abs-Input] [Unit]  [Δ-Toggle] [Δ-Input] [Unit]  [Severity]
	// Layout je Zeile (Delta-only-Metrik):
	//   [Label]                                      [Δ-Toggle] [Δ-Input] [Unit]  [Severity]
	//
	// Werte werden zwei-weg gebunden ueber `state` ($bindable). Disabled-State
	// folgt automatisch dem zugehoerigen Toggle.

	import type { AlertMetric } from '$lib/types';
	import { ALERT_METRIC_LABELS } from '$lib/utils/alertMetricLabels';
	import { DELTA_ONLY_METRICS } from '$lib/components/alert-rules-editor/alertRuleDefaults';
	import type { MetricRowState } from './alertMetricTable.ts';
	import { Select } from '$lib/components/ui/select';

	let {
		metric,
		state = $bindable<MetricRowState>()
	}: { metric: AlertMetric; state: MetricRowState } = $props();

	let info = $derived(ALERT_METRIC_LABELS[metric]);
	let isDeltaOnly = $derived(DELTA_ONLY_METRICS.has(metric));
	let absStep = $derived(metric === 'thunder_level' ? '1' : '0.1');
	let absMin = $derived(metric === 'thunder_level' ? '1' : undefined);

	function toggleAbs() { state.absEnabled = !state.absEnabled; }
	function toggleDelta() { state.deltaEnabled = !state.deltaEnabled; }
</script>

<div class="metric-row" data-testid="alert-metric-row-{metric}">
	<span class="label">{info?.label_de ?? metric}</span>

	{#if !isDeltaOnly}
		<button
			type="button"
			class="toggle"
			class:on={state.absEnabled}
			data-testid="alert-metric-abs-toggle-{metric}"
			aria-pressed={state.absEnabled}
			onclick={toggleAbs}
		>{state.absEnabled ? 'An' : 'Aus'}</button>
		<input
			type="number"
			step={absStep}
			min={absMin}
			class="num-input"
			data-testid="alert-metric-abs-threshold-{metric}"
			bind:value={state.absThreshold}
			disabled={!state.absEnabled}
		/>
		<span class="unit">{info?.unit ?? ''}</span>
	{:else}
		<span class="spacer" aria-hidden="true"></span>
	{/if}

	<button
		type="button"
		class="toggle"
		class:on={state.deltaEnabled}
		data-testid="alert-metric-delta-toggle-{metric}"
		aria-pressed={state.deltaEnabled}
		onclick={toggleDelta}
	>Δ {state.deltaEnabled ? 'An' : 'Aus'}</button>
	<input
		type="number"
		step="0.1"
		min="0"
		class="num-input"
		data-testid="alert-metric-delta-threshold-{metric}"
		bind:value={state.deltaThreshold}
		disabled={!state.deltaEnabled}
	/>
	<span class="unit">{info?.unit ?? ''}</span>

	<Select
		class="severity-select"
		data-testid="alert-metric-severity-{metric}"
		bind:value={state.severity}
	>
		<option value="info">Info</option>
		<option value="warning">Warnung</option>
		<option value="critical">Kritisch</option>
	</Select>
</div>

<style>
	.metric-row {
		display: grid;
		grid-template-columns: 11rem 4.5rem 6rem 3rem 4.5rem 6rem 3rem 1fr;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.25rem;
		border-bottom: 1px solid var(--g-ink-faint);
		font-size: 0.875rem;
	}
	.metric-row:last-child {
		border-bottom: none;
	}
	.label {
		font-weight: 500;
	}
	.spacer {
		grid-column: span 3;
	}
	.toggle {
		min-height: 36px;
		padding: 0.25rem 0.5rem;
		border-radius: 0.25rem;
		border: 1px solid var(--g-ink-faint);
		background: var(--g-surface-1, #fff);
		font-size: 0.8125rem;
		cursor: pointer;
	}
	.toggle.on {
		background: var(--g-accent);
		color: #fff;
		border-color: var(--g-accent);
	}
	.num-input {
		min-height: 36px;
		padding: 0.25rem 0.5rem;
		border: 1px solid var(--g-ink-faint);
		border-radius: 0.25rem;
		width: 100%;
		box-sizing: border-box;
	}
	.num-input:disabled {
		background: var(--g-surface-2);
		color: var(--g-ink-muted);
	}
	.unit {
		font-size: 0.8125rem;
		color: var(--g-ink-muted);
	}
	.severity-select {
		min-height: 36px;
		padding: 0.25rem 0.5rem;
		border: 1px solid var(--g-ink-faint);
		border-radius: 0.25rem;
		background: var(--g-surface-1, #fff);
	}
	@media (max-width: 720px) {
		.metric-row {
			grid-template-columns: 1fr 1fr;
		}
		.spacer {
			display: none;
		}
	}
</style>
