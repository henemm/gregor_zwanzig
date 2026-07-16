<script lang="ts">
	// Issue #364 — eine Zeile in einer BucketSection ("Spalten" / "Detail-Werte").
	// Index (nur primary) · Label+Kürzel · Roh/Skala-Toggle bzw. "nur Rohwert" ·
	// →Detail/✕ (primary) bzw. ↑Spalte/✕ (secondary).
	// Issue #1272: die ▲/▼-Buttons sind ersatzlos entfallen — sortiert wird per
	// Ziehen am Griff bzw. über dessen Tastatur-Pfad (ADR-0024).
	// Design: docs/design/epic_331_output_layout/screen-metrics-editor.jsx
	import type { MetricEntry } from './metricsEditor.ts';

	interface Props {
		metric: MetricEntry;
		short: string;
		bucket: 'primary' | 'secondary';
		index: number;
		isOverLimit: boolean;
		hasIndicator: boolean;
		useIndicator: boolean;
		/** Issue #587: wenn true, wird der "→ Detail"-Knopf in primary ausgeblendet. */
		hideDetailButton?: boolean;
		onMode: (useIndicator: boolean) => void;
		onMove: (target: 'primary' | 'secondary' | 'off') => void;
	}
	let {
		metric, short, bucket, index, isOverLimit,
		hasIndicator, useIndicator, hideDetailButton = false,
		onMode, onMove,
	}: Props = $props();
</script>

<div
	class="row"
	class:over-limit={isOverLimit}
	class:with-index={bucket === 'primary'}
	data-testid="active-metric-row-{metric.id}"
>
	{#if bucket === 'primary'}
		<div class="idx mono" class:warn={isOverLimit}>{index + 1}</div>
	{/if}

	<div class="label-cell">
		<div class="label">{metric.label}</div>
		<div class="meta mono">{metric.unit || '—'} · Kürzel <span class="short">{short}</span></div>
	</div>

	<div class="mode-cell">
		{#if hasIndicator}
			<div class="mode-toggle" role="group" aria-label="Roh oder Einfach">
				<button
					type="button"
					class="mode-btn mono"
					class:active={!useIndicator}
					data-testid="metric-mode-raw-{metric.id}"
					onclick={() => onMode(false)}
				>Roh</button>
				<button
					type="button"
					class="mode-btn mono"
					class:active={useIndicator}
					data-testid="metric-mode-scale-{metric.id}"
					onclick={() => onMode(true)}
				>Einfach</button>
			</div>
		{:else}
			<span class="raw-only mono">nur Rohwert</span>
		{/if}
	</div>

	<div class="move-cell">
		{#if bucket === 'primary'}
			{#if !hideDetailButton}
				<button type="button" class="text-btn" data-testid="metric-to-detail-{metric.id}" onclick={() => onMove('secondary')}>→ Detail</button>
			{/if}
			<button type="button" class="text-btn" data-testid="metric-to-off-{metric.id}" onclick={() => onMove('off')}>✕</button>
		{:else}
			<button type="button" class="text-btn" data-testid="metric-to-column-{metric.id}" onclick={() => onMove('primary')}>↑ Spalte</button>
			<button type="button" class="text-btn" data-testid="metric-to-off-{metric.id}" onclick={() => onMove('off')}>✕</button>
		{/if}
	</div>
</div>

<style>
	.row {
		display: grid;
		grid-template-columns: 1fr 200px 150px;
		gap: var(--g-s-3);
		align-items: center;
		padding: var(--g-s-3) var(--g-s-5);
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.row.with-index {
		grid-template-columns: 30px 1fr 200px 150px;
	}
	.row.over-limit {
		background: color-mix(in srgb, var(--g-warning) 4%, transparent);
	}
	.idx {
		font-size: var(--g-text-xs);
		font-weight: 600;
		color: var(--g-ink-muted);
		text-align: right;
	}
	.idx.warn {
		color: var(--g-warning);
	}
	.label-cell {
		min-width: 0;
	}
	.label {
		font-size: var(--g-text-sm);
		font-weight: 500;
		color: var(--g-ink);
	}
	.meta {
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
		margin-top: 2px;
	}
	.short {
		color: var(--g-ink-muted);
	}
	.mode-toggle {
		display: inline-flex;
		padding: 2px;
		background: var(--g-surface-1);
		border-radius: var(--g-radius-xs);
		border: 1px solid var(--g-rule-soft);
	}
	.mode-btn {
		padding: var(--g-s-1) var(--g-s-3);
		font-size: var(--g-text-xs);
		font-weight: 600;
		border: none;
		cursor: pointer;
		border-radius: var(--g-radius-xs);
		background: transparent;
		color: var(--g-ink-muted);
		letter-spacing: var(--g-track-wide);
	}
	.mode-btn.active {
		background: var(--g-paper);
		color: var(--g-accent-deep);
		box-shadow: 0 0 0 1px var(--g-ink-faint);
	}
	.raw-only {
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
		letter-spacing: var(--g-track-wide);
		text-transform: uppercase;
	}
	.move-cell {
		display: flex;
		gap: var(--g-s-1);
	}
	.text-btn {
		padding: var(--g-s-1) var(--g-s-2);
		font-size: var(--g-text-xs);
		font-weight: 500;
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-xs);
		background: var(--g-surface-0);
		color: var(--g-ink-muted);
		cursor: pointer;
		white-space: nowrap;
	}
</style>
