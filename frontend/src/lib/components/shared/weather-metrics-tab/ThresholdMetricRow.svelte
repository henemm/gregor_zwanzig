<script lang="ts">
	// Issue #872 — Eine Schwellwert-Metrik-Zeile im Inhalt-Reiter: Segmented-Control
	// (3 Stufen Sensibel/Standard/Robust, bzw. 2 Stufen MED/HIGH bei Gewitter)
	// + aktueller Wert. Analog zu AlertMetricLevelRow.svelte.
	// Spec: docs/specs/modules/issue_872_threshold_ux.md

	interface Level {
		id: string; // 'sensibel' | 'standard' | 'robust' | 'med' | 'high'
		label: string;
		float: number;
	}

	interface Props {
		metricId: string;
		label: string;
		levels: Level[];
		currentFloat: number | null;
		onChange: (metricId: string, float: number) => void;
		// Issue #1318 AC-9: SMS-Kuerzel dieser Metrik, aus dem Backend-Katalog
		// (/api/sms-symbols). Fehlt es, entfaellt die Anzeige ersatzlos.
		smsSymbol?: string;
	}

	let { metricId, label, levels, currentFloat, onChange, smsSymbol }: Props = $props();

	// Reverse-Mapping: aktive Stufe aus currentFloat. Kein Treffer → erste Stufe (Fallback).
	const activeId = $derived(
		levels.find((l) => l.float === currentFloat)?.id ?? levels[0]?.id ?? ''
	);
	const activeFloat = $derived(levels.find((l) => l.id === activeId)?.float ?? null);
	const valueDisplay = $derived(activeFloat !== null ? String(activeFloat) : '—');
</script>

<tr data-testid="threshold-metric-row-{metricId}" data-metric={metricId}>
	<td class="metric-label">
		{label}
		{#if smsSymbol}<code class="sms-symbol" data-testid="sms-symbol-{metricId}">{smsSymbol}</code>{/if}
	</td>
	<td class="segmented-control" data-testid="threshold-segmented-{metricId}">
		{#each levels as l (l.id)}
			<button
				type="button"
				class:active={activeId === l.id}
				onclick={() => onChange(metricId, l.float)}
				aria-pressed={activeId === l.id}
				data-testid="threshold-level-{metricId}-{l.id}"
			>
				{l.label}
			</button>
		{/each}
	</td>
	<td class="threshold" data-testid="threshold-value-{metricId}">{valueDisplay}</td>
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

	.threshold {
		padding: 8px;
		font-family: var(--g-font-mono, monospace);
		font-size: 13px;
		color: var(--g-ink-2, #555);
		white-space: nowrap;
	}

	.segmented-control {
		display: flex;
		gap: 2px;
		padding: 8px;
	}

	.segmented-control button {
		min-height: 44px;
		padding: 8px 10px;
		border: 1px solid var(--g-rule, #ddd);
		background: transparent;
		color: var(--g-ink);
		cursor: pointer;
		font-size: 14px;
	}

	.segmented-control button.active {
		background: var(--g-accent, #2563eb);
		color: white;
		border-color: var(--g-accent, #2563eb);
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

		.metric-label {
			display: inline-block;
			font-weight: 600;
		}

		.threshold {
			display: inline-block;
			margin-left: 8px;
		}

		.segmented-control {
			width: 100%;
			padding: 8px 0 0;
		}

		.segmented-control button {
			flex: 1;
			font-size: 16px; /* verhindert iOS-Zoom */
		}
	}
</style>
