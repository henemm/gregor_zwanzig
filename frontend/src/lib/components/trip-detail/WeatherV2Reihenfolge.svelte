<script lang="ts">
	// Issue #587 — Wetter-Metriken-Tab v2: Abschnitt 3 Reihenfolge & Darstellung.
	// 1:1 nach WM2_Reihenfolge / WM2_ReihenfolgeRow / WM2_CutLine aus JSX.
	// Kein „→ Detail"-Knopf, keine Detail-Zeile (PO-Entscheidung 2026-06-06).
	// Orange gestrichelte Schnittlinie nach Position 8 NUR wenn activeChannel=telegram.
	import type { MetricEntry } from './metricsEditor.ts';
	import { indicatorCapable, CHANNEL_COL_BUDGET } from './metricsEditor.ts';
	import type { Highlight } from './metricsEditor.ts';
	import { Segmented } from '$lib/components/atoms';

	interface Props {
		primaryColumns: string[];
		metricById: Record<string, MetricEntry>;
		friendlyMap: Record<string, boolean>;
		activeChannel: string;
		highlight: Highlight | null;
		onRemove: (id: string) => void;
		onReorder: (id: string, dir: -1 | 1) => void;
		onMode: (id: string, useIndicator: boolean) => void;
	}

	let { primaryColumns, metricById, friendlyMap, activeChannel, highlight, onRemove, onReorder, onMode }: Props = $props();

	const tgBudget = CHANNEL_COL_BUDGET.telegram;
	const showCutLine = $derived(activeChannel === 'telegram');
</script>

<div class="reihenfolge" data-testid="wm2-reihenfolge">
	<div class="section-subhead">
		Reihenfolge
		<span class="count">· {primaryColumns.length} Metriken</span>
		<span class="hint-right mono">links → rechts in der Email-Tabelle</span>
	</div>
	<div class="rows">
		{#each primaryColumns as id, i}
			{@const m = metricById[id]}
			{@const hl = highlight && highlight.id === id}
			{@const hasInd = indicatorCapable(id)}
			{@const useIndicator = friendlyMap[id] === true}
			{#if showCutLine && i === tgBudget}
				<div class="cut-line" data-testid="wm2-cut-line">
					<span class="cut-scissors" aria-hidden="true">✂</span>
					<span class="mono">ab hier Telegram-Limit — weiter vorne = sicherer in der Tabelle (max {tgBudget} Spalten)</span>
				</div>
			{/if}
			<div
				class="row"
				class:hl
				data-testid="wm2-reihenfolge-row"
				data-metric-id={id}
			>
				<div class="pos mono">{i + 1}</div>
				<svg class="drag-dots" width="10" height="14" viewBox="0 0 10 14" fill="var(--g-ink-4)" aria-hidden="true">
					<circle cx="3" cy="3" r="1.1"/><circle cx="7" cy="3" r="1.1"/>
					<circle cx="3" cy="7" r="1.1"/><circle cx="7" cy="7" r="1.1"/>
					<circle cx="3" cy="11" r="1.1"/><circle cx="7" cy="11" r="1.1"/>
				</svg>
				<div class="label-cell">
					{#if m}
						<span class="metric-label">{m.label}</span>
						{#if m.unit}
							<span class="metric-unit mono">{m.unit}</span>
						{/if}
					{:else}
						<span class="metric-label">{id}</span>
					{/if}
				</div>
				<div class="controls">
					{#if hasInd}
						<Segmented
							size="sm"
							value={useIndicator ? 'indicator' : 'raw'}
							onChange={(v: string) => onMode(id, v === 'indicator')}
							items={[{ id: 'raw', label: 'Roh' }, { id: 'indicator', label: 'Einfach' }]}
						/>
					{/if}
					<button
						type="button"
						class="btn-aus"
						onclick={() => onRemove(id)}
						title="Aus Briefing entfernen"
					>
						Aus
					</button>
					<div class="arrow-group">
						<button
							type="button"
							class="arrow-btn"
							disabled={i === 0}
							onclick={() => onReorder(id, -1)}
							aria-label="Nach oben"
						>
							<svg width="11" height="11" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
								<path d="M6 2.5L10 8H2Z"/>
							</svg>
						</button>
						<button
							type="button"
							class="arrow-btn"
							disabled={i === primaryColumns.length - 1}
							onclick={() => onReorder(id, 1)}
							aria-label="Nach unten"
						>
							<svg width="11" height="11" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
								<path d="M6 9.5L2 4H10Z"/>
							</svg>
						</button>
					</div>
				</div>
			</div>
		{/each}
	</div>
</div>

<style>
	.reihenfolge {
		display: flex;
		flex-direction: column;
		gap: 0;
	}
	.section-subhead {
		display: flex;
		align-items: baseline;
		gap: 0;
		padding: 14px 16px 10px;
		border-bottom: 1px solid var(--g-rule-soft);
		font-size: 16px;
		font-weight: 600;
		color: var(--g-ink);
	}
	.count {
		color: var(--g-ink-4);
		font-weight: 400;
		font-size: 13px;
		margin-left: 4px;
	}
	.hint-right {
		font-size: 10px;
		color: var(--g-ink-4);
		margin-left: auto;
	}
	.rows {
		display: flex;
		flex-direction: column;
	}
	.row {
		display: grid;
		grid-template-columns: 28px 16px 1fr auto;
		gap: 10px;
		padding: 10px 16px;
		border-bottom: 1px solid var(--g-rule-soft);
		align-items: center;
		background: transparent;
		transition: background 0.3s;
	}
	.row.hl {
		background: var(--g-accent-tint);
	}
	.pos {
		font-size: 11px;
		font-weight: 600;
		color: var(--g-ink-4);
		text-align: right;
	}
	.drag-dots {
		opacity: 0.5;
		flex-shrink: 0;
	}
	.label-cell {
		display: flex;
		align-items: baseline;
		gap: 0;
		min-width: 0;
	}
	.metric-label {
		font-size: 13.5px;
		font-weight: 500;
		color: var(--g-ink);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.metric-unit {
		font-size: 10.5px;
		color: var(--g-ink-4);
		margin-left: 6px;
		white-space: nowrap;
	}
	.controls {
		display: flex;
		gap: 8px;
		align-items: center;
		justify-content: flex-end;
		flex-wrap: wrap;
	}
	.btn-aus {
		padding: 5px 9px;
		font-size: 11.5px;
		font-family: inherit;
		font-weight: 500;
		border: 1px solid rgba(168, 50, 50, 0.35);
		border-radius: 3px;
		background: var(--g-card);
		color: var(--g-bad);
		cursor: pointer;
		white-space: nowrap;
	}
	.btn-aus:hover {
		background: rgba(168, 50, 50, 0.06);
	}
	.arrow-group {
		display: flex;
		gap: 2px;
	}
	.arrow-btn {
		width: 26px;
		height: 26px;
		border: 1px solid var(--g-rule);
		border-radius: 3px;
		background: var(--g-card);
		color: var(--g-ink-2);
		cursor: pointer;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0;
		transition: opacity 120ms;
	}
	.arrow-btn:disabled {
		cursor: not-allowed;
		opacity: 0.3;
	}
	.cut-line {
		padding: 6px 16px;
		font-size: 10.5px;
		color: #8a6210;
		background: rgba(192, 138, 26, 0.07);
		border-top: 1.5px dashed var(--g-warn);
		border-bottom: 1.5px dashed var(--g-warn);
		display: flex;
		align-items: center;
		gap: 7px;
	}
	.cut-scissors {
		flex-shrink: 0;
	}
</style>
