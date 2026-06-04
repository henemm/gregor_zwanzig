<script lang="ts">
	// Issue #180 — Eine Zeile der Schwellwert-Tabelle.
	// Issue #586 — 4-Spalten-Grid nach JSX + Zeilen-Switch + Label+Unit-Spalte.

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

	let rowEnabled = $derived(state.absEnabled || state.deltaEnabled);

	function toggleRow() {
		const enable = !rowEnabled;
		if (enable) {
			state.deltaEnabled = true;
			if (!isDeltaOnly) state.absEnabled = true;
		} else {
			state.absEnabled = false;
			state.deltaEnabled = false;
		}
	}
</script>

<div class="metric-row" class:disabled={!rowEnabled} data-testid="alert-metric-row-{metric}">
	<!-- Col 1: Row toggle switch -->
	<label style="cursor: pointer; display: flex; align-items: center;">
		<span
			class="row-switch"
			class:on={rowEnabled}
			onclick={toggleRow}
			role="switch"
			aria-checked={rowEnabled}
			tabindex="0"
			onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleRow(); } }}
			data-testid="alert-metric-row-toggle-{metric}"
		>
			<span class="row-switch-knob"></span>
		</span>
	</label>

	<!-- Col 2: Label + Unit -->
	<div>
		<div class="metric-label">{info?.label_de ?? metric}</div>
		<div class="metric-unit">{info?.unit ?? ''}</div>
	</div>

	<!-- Col 3: Delta threshold -->
	<div>
		{#if state.deltaEnabled}
			<div class="threshold-row">
				<span class="threshold-label">Δ ≥</span>
				<input
					type="number"
					step="0.1"
					min="0"
					class="threshold-input"
					data-testid="alert-metric-delta-threshold-{metric}"
					bind:value={state.deltaThreshold}
				/>
				<span class="threshold-unit">{info?.unit ?? ''}</span>
			</div>
		{:else}
			<span class="disabled-label">— deaktiviert —</span>
		{/if}
	</div>

	<!-- Col 4: Absolute threshold -->
	<div>
		{#if state.absEnabled && !isDeltaOnly}
			<div class="threshold-row">
				<span class="threshold-label">{info?.comparison ?? '>'}</span>
				<input
					type="number"
					step={absStep}
					min={absMin}
					class="threshold-input"
					data-testid="alert-metric-abs-threshold-{metric}"
					bind:value={state.absThreshold}
				/>
				<span class="threshold-unit">{info?.unit ?? ''}</span>
			</div>
		{:else}
			<span class="disabled-label">— deaktiviert —</span>
		{/if}
	</div>

	<!-- Col 5: Severity (functional extension, kept as 5th column) -->
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
		grid-template-columns: 32px 200px 1fr 1fr auto;
		gap: 0;
		padding: 14px 20px;
		border-bottom: 1px solid var(--g-rule-soft);
		align-items: center;
	}
	.metric-row.disabled {
		opacity: 0.45;
	}
	.metric-row:last-child {
		border-bottom: none;
	}
	.row-switch {
		display: inline-block;
		width: 30px;
		height: 16px;
		border-radius: 9px;
		background: var(--g-rule);
		position: relative;
		transition: background 120ms;
		cursor: pointer;
		flex-shrink: 0;
	}
	.row-switch.on {
		background: var(--g-accent);
	}
	.row-switch-knob {
		position: absolute;
		top: 2px;
		left: 2px;
		width: 12px;
		height: 12px;
		border-radius: 50%;
		background: #fff;
		transition: left 120ms;
	}
	.row-switch.on .row-switch-knob {
		left: 16px;
	}
	.metric-label {
		font-size: 13px;
		font-weight: 600;
	}
	.metric-unit {
		font-size: 10px;
		color: var(--g-ink-4);
		font-family: var(--g-font-mono);
	}
	.threshold-row {
		display: flex;
		align-items: baseline;
		gap: 6px;
	}
	.threshold-label {
		font-size: 11px;
		color: var(--g-ink-3);
		font-family: var(--g-font-mono);
	}
	.threshold-unit {
		font-size: 11px;
		color: var(--g-ink-3);
		font-family: var(--g-font-mono);
	}
	.threshold-input {
		width: 64px;
		padding: 6px 8px;
		border: 1px solid var(--g-rule);
		border-radius: 3px;
		font-size: 13px;
		font-family: var(--g-font-mono);
		text-align: right;
	}
	.disabled-label {
		font-size: 11px;
		color: var(--g-ink-4);
		font-family: var(--g-font-mono);
	}
	:global(.severity-select) {
		min-height: 36px;
		padding: 0.25rem 0.5rem;
		border: 1px solid var(--g-ink-faint);
		border-radius: 0.25rem;
		background: var(--g-surface-1, #fff);
	}
	@media (max-width: 720px) {
		.metric-row {
			grid-template-columns: 32px 1fr;
			flex-wrap: wrap;
		}
	}
</style>
