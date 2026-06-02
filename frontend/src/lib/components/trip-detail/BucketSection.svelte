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
	import { dndzone, type DndEvent } from 'svelte-dnd-action';
	import { flip } from 'svelte/animate';

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
		onMode: (id: string, useIndicator: boolean) => void;
		onMove: (id: string, target: 'primary' | 'secondary' | 'off') => void;
		onReorder: (id: string, dir: -1 | 1) => void;
		onDndReorder: (newOrder: string[]) => void;
	}
	let {
		eyebrow, title, hint, bucket, items, metricById, shortById,
		friendlyMap, indicatorCapable, showLimitMarkers = false,
		onMode, onMove, onReorder, onDndReorder,
	}: Props = $props();

	const signalBudget = CHANNEL_COL_BUDGET.signal; // 5 wählbare Spalten

	// dndzone braucht Array<{id: string}>. Ein $effect (NICHT die abgeleitete
	// Variante!) synct items in den lokalen DnD-State, weil dndzone die Liste
	// während der consider-Phase mit einem Phantom-Placeholder mutiert — eine
	// abgeleitete Variable würde den Drag-Zustand pro Tick zurücksetzen.
	let dndItems = $state<{ id: string }[]>([]);

	$effect(() => {
		dndItems = items.map((id) => ({ id }));
	});

	function handleDndConsider(e: CustomEvent<DndEvent<{ id: string }>>) {
		dndItems = e.detail.items;
	}

	function handleDndFinalize(e: CustomEvent<DndEvent<{ id: string }>>) {
		dndItems = e.detail.items;
		onDndReorder(dndItems.map((x) => x.id));
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
		<div
			use:dndzone={{ items: dndItems, flipDurationMs: 200, dropTargetStyle: {}, dropFromOthersDisabled: true }}
			onconsider={handleDndConsider}
			onfinalize={handleDndFinalize}
		>
			{#each dndItems as item, i (item.id)}
				<div animate:flip={{ duration: 200 }}>
					{#if bucket === 'primary' && i === signalBudget}
						<div class="signal-divider mono" data-testid="signal-divider">
							↓ ab hier bei <strong>Signal</strong> automatisch als Detail-Zeile (max {signalBudget} Spalten)
						</div>
					{/if}
					{#if metricById[item.id]}
						<ActiveMetricRow
							metric={metricById[item.id]}
							short={shortById[item.id] ?? metricById[item.id].label.slice(0, 5)}
							{bucket}
							index={i}
							isFirst={i === 0}
							isLast={i === items.length - 1}
							isOverLimit={bucket === 'primary' && i >= signalBudget}
							hasIndicator={indicatorCapable(item.id)}
							useIndicator={friendlyMap[item.id] ?? true}
							onMode={(v) => onMode(item.id, v)}
							onMove={(t) => onMove(item.id, t)}
							onReorder={(d) => onReorder(item.id, d)}
						/>
					{/if}
				</div>
			{/each}
		</div>
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
	.signal-divider {
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
