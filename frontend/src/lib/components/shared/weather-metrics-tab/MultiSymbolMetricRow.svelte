<script lang="ts">
	// Fix #1613 — Anzeigezeile fuer Metriken mit MEHREREN SMS-Kuerzeln
	// (wind_chill: FN/FK/FD/WC, temperature: K/D, temperature_night: N).
	// Analog ThresholdMetricRow.svelte, aber ohne Segmented-Control/Schwellwert
	// -- diese Metriken haben keinen konfigurierbaren SMS-Schwellwert.
	// Spec: docs/specs/modules/fix_1613_sms_multi_symbols.md

	interface Props {
		metricId: string;
		label: string;
		symbols: string[];
	}

	let { metricId, label, symbols }: Props = $props();
</script>

<tr data-testid="sms-multi-symbol-row-{metricId}" data-metric={metricId}>
	<td class="metric-label" colspan="3">
		{label}
		{#each symbols as symbol (symbol)}
			<code class="sms-symbol" data-testid="sms-symbol-badge-{metricId}-{symbol}">{symbol}</code>
		{/each}
	</td>
</tr>

<style>
	.metric-label {
		padding: 8px;
		font-size: 14px;
		color: var(--g-ink);
	}

	.sms-symbol {
		font-family: var(--g-font-mono, monospace);
		font-size: 12px;
		color: var(--g-ink-2, #555);
		margin-left: 4px;
	}

	@media (max-width: 899px) {
		tr {
			display: block;
			margin-bottom: 12px;
			border-bottom: 1px solid var(--g-rule-soft, #eee);
			padding-bottom: 8px;
		}

		td {
			display: block;
		}
	}
</style>
