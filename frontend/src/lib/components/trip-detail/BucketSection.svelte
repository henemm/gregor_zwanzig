<script lang="ts">
	// Issue #364 — Bucket-Sektion "Spalten" (primary) oder "Detail-Werte"
	// (secondary). Header (Eyebrow/Title/Count/Hint) + optional ChannelLimit-
	// Markers + Signal-Trenner ab der 6. Spalte + Zeilen.
	// Design: docs/design/epic_331_output_layout/screen-metrics-editor.jsx
	import { Eyebrow } from '$lib/components/atoms';
	import * as Card from '$lib/components/ui/card/index.js';
	import ActiveMetricRow from './ActiveMetricRow.svelte';
	import { CHANNEL_COL_BUDGET, type MetricEntry } from './metricsEditor.ts';
	import ChannelLimitMarkers from './ChannelLimitMarkers.svelte';
	import SortableList from '$lib/components/shared/dnd/SortableList.svelte';
	import DragHandle from '$lib/components/shared/dnd/DragHandle.svelte';

	interface Props {
		eyebrow: string;
		title: string;
		hint: string;
		bucket: 'primary' | 'secondary';
		items: string[];
		metricById: Record<string, MetricEntry>;
		shortById: Record<string, string>;
		friendlyMap: Record<string, boolean>;
		indicatorCapable: (id: string) => boolean;
		showLimitMarkers?: boolean;
		/** Issue #587: wenn true, wird der "→ Detail"-Knopf in jeder Zeile ausgeblendet. */
		hideDetailButton?: boolean;
		onMode: (id: string, useIndicator: boolean) => void;
		onMove: (id: string, target: 'primary' | 'secondary' | 'off') => void;
		onDndReorder: (newOrder: string[]) => void;
	}
	let {
		eyebrow, title, hint, bucket, items, metricById, shortById,
		friendlyMap, indicatorCapable, showLimitMarkers = false,
		hideDetailButton = false,
		onMode, onMove, onDndReorder,
	}: Props = $props();

	const telegramBudget = CHANNEL_COL_BUDGET.telegram; // #587: 8 wählbare Spalten (war 7)

	// Issue #1272: DnD-State/Sync/Flip liegen jetzt im geteilten SortableList
	// (ADR-0024). Der Telegram-Trenner ist bedingtes Markup INNERHALB des
	// Item-Wrappers — als Sibling in der Zone würde dndzone ihn entfernen.
	function itemLabel(id: string, i: number) {
		return `${i + 1}. ${metricById[id]?.label ?? id}`;
	}
</script>

<Card.Root data-testid="bucket-section-{bucket}">
	<div class="head">
		<div class="head-top">
			<div>
				<Eyebrow>{eyebrow}</Eyebrow>
				<div class="title">{title} <span class="count">· {items.length}</span></div>
			</div>
			{#if showLimitMarkers}
				<ChannelLimitMarkers count={items.length} />
			{/if}
		</div>
		<div class="hint">{hint}</div>
	</div>

	{#if items.length === 0}
		<div class="empty">Keine Einträge — Metriken aus „Nicht im Briefing" hinzufügen.</div>
	{:else}
		<SortableList
			{items}
			{onDndReorder}
			ariaLabel="{title}, Reihenfolge"
			{itemLabel}
			dropFromOthersDisabled
		>
			{#snippet row(id: string, i: number)}
				{#if bucket === 'primary' && i === telegramBudget}
					<div class="telegram-divider mono" data-testid="telegram-divider">
						✂ ab hier bei <strong>Telegram</strong> abgeschnitten (max {telegramBudget} Spalten)
					</div>
				{/if}
				{#if metricById[id]}
					<div class="row-with-handle">
						<DragHandle />
						<ActiveMetricRow
							metric={metricById[id]}
							short={shortById[id] ?? metricById[id].label.slice(0, 5)}
							{bucket}
							index={i}
							isOverLimit={bucket === 'primary' && i >= telegramBudget}
							hasIndicator={indicatorCapable(id)}
							useIndicator={friendlyMap[id] ?? true}
							{hideDetailButton}
							onMode={(v) => onMode(id, v)}
							onMove={(t) => onMove(id, t)}
						/>
					</div>
				{/if}
			{/snippet}
		</SortableList>
	{/if}
</Card.Root>

<style>
	.head {
		padding: var(--g-s-4) var(--g-s-5) var(--g-s-3);
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.head-top {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: var(--g-s-3);
	}
	.title {
		font-size: var(--g-text-xl);
		font-weight: 600;
		margin-top: 2px;
		letter-spacing: var(--g-track-tight);
	}
	.count {
		color: var(--g-ink-muted);
		font-weight: 400;
		font-size: var(--g-text-sm);
	}
	.hint {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		margin-top: var(--g-s-2);
		line-height: 1.5;
		max-width: 760px;
	}
	.empty {
		padding: var(--g-s-5);
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		font-style: italic;
		text-align: center;
	}
	.row-with-handle {
		display: grid;
		grid-template-columns: auto 1fr;
		align-items: center;
	}
	.row-with-handle :global(.drag-handle) {
		padding-left: var(--g-s-5);
	}
	.telegram-divider {
		padding: var(--g-s-1) var(--g-s-5);
		font-size: var(--g-text-xs);
		letter-spacing: var(--g-track-caps);
		text-transform: uppercase;
		color: var(--g-warning);
		background: color-mix(in srgb, var(--g-warning) 6%, transparent);
		border-top: 1px dashed var(--g-warning);
		border-bottom: 1px dashed var(--g-warning);
	}
</style>
