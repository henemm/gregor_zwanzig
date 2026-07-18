<script lang="ts">
	// Issue #587 — Wetter-Metriken-Tab v2: Abschnitt 3 Reihenfolge & Darstellung.
	// 1:1 nach WM2_Reihenfolge / WM2_ReihenfolgeRow / WM2_CutLine aus JSX.
	// Kein „→ Detail"-Knopf, keine Detail-Zeile (PO-Entscheidung 2026-06-06).
	// Orange gestrichelte Schnittlinie nach Position 8 NUR wenn activeChannel=telegram.
	// Issue #848 — Drag & Drop ersetzt Pfeiltasten.
	// Issue #1272 / ADR-0024 — handverdrahtetes HTML5-Drag raus, geteilter
	// Baustein `shared/dnd/SortableList` rein. Vertrag jetzt
	// onDndReorder(newOrder: string[]) statt (fromId, toId). Die Cut-Line ist
	// bedingtes Markup INNERHALB des Item-Wrappers — als Sibling in der Zone
	// wuerde `dndzone` sie aus dem DOM entfernen.
	// Issue #1232 Scheibe 3b: Cut-Line-Markup durch geteiltes Primitiv
	// `LTCutLine` ersetzt (KL-1 aus Scheibe 3a wird hiermit aufgelöst).
	import type { MetricEntry } from '../../trip-detail/metricsEditor.ts';
	import { indicatorCapable, CHANNEL_COL_BUDGET } from '../../trip-detail/metricsEditor.ts';
	import type { Highlight } from '../../trip-detail/metricsEditor.ts';
	import { Segmented } from '$lib/components/atoms';
	import LTCutLine from '$lib/components/shared/layout-tab/LTCutLine.svelte';
	import SortableList from '$lib/components/shared/dnd/SortableList.svelte';
	import DragHandle from '$lib/components/shared/dnd/DragHandle.svelte';

	interface Props {
		primaryColumns: string[];
		metricById: Record<string, MetricEntry>;
		friendlyMap: Record<string, boolean>;
		activeChannel: string;
		highlight: Highlight | null;
		onRemove: (id: string) => void;
		onDndReorder: (newOrder: string[]) => void;
		onMode: (id: string, useIndicator: boolean) => void;
	}

	let { primaryColumns, metricById, friendlyMap, activeChannel, highlight, onRemove, onDndReorder, onMode }: Props = $props();

	const tgBudget = CHANNEL_COL_BUDGET.telegram;
	const showCutLine = $derived(activeChannel === 'telegram');

	function itemLabel(id: string, i: number): string {
		return `${i + 1}. ${metricById[id]?.label ?? id}`;
	}
</script>

<div class="reihenfolge" data-testid="wm2-reihenfolge">
	<div class="section-subhead">
		Reihenfolge
		<span class="count">· {primaryColumns.length} Metriken</span>
		<span class="hint-right mono">links → rechts in der Email-Tabelle</span>
	</div>
	<SortableList
		items={primaryColumns}
		{onDndReorder}
		ariaLabel="Metriken, Reihenfolge"
		{itemLabel}
	>
		{#snippet row(id: string, i: number)}
			{@const m = metricById[id]}
			{@const hl = highlight && highlight.id === id}
			{@const hasInd = indicatorCapable(id)}
			{@const useIndicator = friendlyMap[id] === true}
			{#if showCutLine && i === tgBudget}
				<div data-testid="wm2-cut-line">
					<LTCutLine label="Telegram" max={tgBudget} />
				</div>
			{/if}
			<div class="row" class:hl data-testid="wm2-reihenfolge-row" data-metric-id={id}>
				<div class="pos mono">{i + 1}</div>
				<DragHandle size={14} />
				<div class="label-cell">
					{#if m}
						<span class="metric-label">{m.label}</span>
						{#if m.unit}
							<span class="metric-unit mono">{m.unit}</span>
						{/if}
						{#if m.col_label}
							<span class="col-badge mono">{m.col_label}</span>
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
				</div>
			</div>
		{/snippet}
	</SortableList>
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
	.row {
		display: grid;
		grid-template-columns: 28px 16px 1fr auto;
		gap: 10px;
		padding: 10px 16px;
		border-bottom: 1px solid var(--g-rule-soft);
		border-top: 2px solid transparent;
		align-items: center;
		background: transparent;
		transition: background 0.15s;
		cursor: grab;
	}
	.row:active {
		cursor: grabbing;
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
	.col-badge {
		font-size: 10px;
		color: var(--g-ink-4);
		background: var(--g-paper);
		border: 1px solid var(--g-rule-soft);
		border-radius: 3px;
		padding: 0 4px;
		margin-left: 6px;
		line-height: 1.6;
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
	@media (max-width: 899px) {
		.metric-label {
			white-space: normal;
			overflow: visible;
			text-overflow: clip;
		}
		.label-cell {
			flex-wrap: wrap;
		}
		.controls {
			flex-direction: column;
			align-items: flex-end;
			gap: 4px;
		}
	}
</style>
