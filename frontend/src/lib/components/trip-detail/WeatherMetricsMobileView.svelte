<script lang="ts">
	// Issue #415 — Mobile Wetter-Metriken: Full-Screen-Overlay.
	//
	// Erscheint auf Viewports <= 899px als Overlay (z-index 150) über dem
	// WeatherMetricsTab. Touch-optimierte Konfiguration: Preset-Pills (horizontal
	// scrollbar), Single-Open-Akkordeon mit MSwitch pro Metrik, fixierter Footer.
	//
	// Spec: docs/specs/modules/issue_415_mobile_metrics_view.md
	import type { Trip, MetricPreset } from '$lib/types';
	import MSwitch from '$lib/components/mobile/MSwitch.svelte';
	import MIcon from '$lib/components/mobile/MIcon.svelte';
	import { Btn, Eyebrow } from '$lib/components/atoms';
	import {
		CATEGORY_ORDER, CATEGORY_LABELS,
		type Buckets, type MetricEntry, type MetricCatalog,
	} from './metricsEditor.ts';

	interface Template {
		id: string;
		label: string;
		metrics: string[];
	}
	interface Props {
		trip: Trip;
		catalog: MetricCatalog;
		templates: Template[];
		userPresets: MetricPreset[];
		buckets: Buckets;
		friendlyMap: Record<string, boolean>;
		metricById: Record<string, MetricEntry>;
		selectedTemplate: string;
		savedSnapshot: string;
		isDirty: boolean;
		saving: boolean;
		onToggleMetric: (id: string, active: boolean) => void;
		onSelectPreset: (id: string) => void;
		onSave: () => void;
		onDiscard: () => void;
		onClose: () => void;
		onOpenSavePresetDialog: () => void;
	}
	let {
		trip, catalog, templates, userPresets, buckets,
		friendlyMap, metricById, selectedTemplate, savedSnapshot,
		isDirty, saving,
		onToggleMetric, onSelectPreset, onSave, onDiscard, onClose,
		onOpenSavePresetDialog,
	}: Props = $props();

	let openCat = $state(CATEGORY_ORDER[0]); // Single-Open Akkordeon

	const enabledMap = $derived(
		Object.fromEntries([...buckets.primary, ...buckets.secondary].map((id) => [id, true])),
	);
	const totalActive = $derived(buckets.primary.length + buckets.secondary.length);

	function activeCatCount(cat: string): number {
		return (catalog[cat] ?? []).filter((m) => enabledMap[m.id]).length;
	}

	const totalMetrics = $derived(
		Object.values(catalog).reduce((s, ms) => s + ms.length, 0),
	);
</script>

<div class="mobile-overlay" data-testid="weather-metrics-mobile-view">
	<!-- A) Mini-Header -->
	<header class="overlay-header">
		<button class="icon-btn" aria-label="Zurück" onclick={onClose}>
			<MIcon kind="back" size={22} />
		</button>
		<span class="breadcrumb">{trip.name} · BRIEFING-SPALTEN</span>
		<Btn variant="ghost" size="sm" onclick={onClose}>Abbrechen</Btn>
	</header>

	<!-- B) Preset-Strip -->
	<div class="preset-strip-wrap">
		<Eyebrow>Preset wählen</Eyebrow>
		<div class="preset-strip">
			{#each [...userPresets, ...templates] as p}
				{@const count = 'metrics' in p && Array.isArray(p.metrics)
					? (p.metrics[0] && typeof p.metrics[0] === 'string'
						? p.metrics.length
						: (p.metrics as { enabled: boolean }[]).filter((m) => m.enabled).length)
					: 0}
				<button
					class="preset-pill"
					data-active={selectedTemplate === p.id || undefined}
					onclick={() => onSelectPreset(p.id)}
				>{('label' in p ? p.label : p.name)} · {count}</button>
			{/each}
		</div>
	</div>

	<!-- C) Preset-Info-Zeile -->
	<div class="preset-info">
		<span>{totalActive} von {totalMetrics} Metriken aktiv</span>
		<Btn variant="ghost" size="sm" onclick={onOpenSavePresetDialog}>Als eigen sp.</Btn>
	</div>

	<!-- D) Scrollbarer Mittelteil -->
	<div class="overlay-scroll">
		{#each CATEGORY_ORDER as cat}
			{#if (catalog[cat] ?? []).length > 0}
				<button class="accordion-head" onclick={() => { openCat = openCat === cat ? '' : cat; }}>
					<span class="accordion-label">
						{CATEGORY_LABELS[cat]}
						<span class="accordion-count">{activeCatCount(cat)} / {(catalog[cat] ?? []).length}</span>
					</span>
					<MIcon kind={openCat === cat ? 'chevron-up' : 'chevron-down'} size={18} />
				</button>
				{#if openCat === cat}
					{#each (catalog[cat] ?? []) as metric}
						<div class="metric-row">
							<span class="metric-label">{metric.label}</span>
							{#if metric.unit}<span class="metric-unit">{metric.unit}</span>{/if}
							<MSwitch
								checked={!!enabledMap[metric.id]}
								onchange={(checked) => onToggleMetric(metric.id, checked)}
							/>
						</div>
					{/each}
				{/if}
			{/if}
		{/each}
	</div>

	<!-- E) Fixierter Footer -->
	<footer class="overlay-footer">
		<Btn variant="ghost" onclick={() => { onDiscard(); onClose(); }}>Reset</Btn>
		<Btn variant="primary" disabled={saving} onclick={() => { onSave(); onClose(); }}>{totalActive} übernehmen</Btn>
	</footer>
</div>

<style>
	.mobile-overlay {
		position: fixed;
		inset: 0;
		z-index: 150;
		background: var(--g-paper);
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}
	.overlay-header {
		display: flex;
		align-items: center;
		gap: var(--g-s-2);
		padding: var(--g-s-3) var(--g-s-4);
		border-bottom: 1px solid var(--g-ink-faint);
		flex-shrink: 0;
	}
	.icon-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		background: none;
		border: none;
		cursor: pointer;
		padding: 0;
		color: var(--g-ink);
	}
	.breadcrumb {
		flex: 1;
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}
	.preset-strip-wrap {
		padding: var(--g-s-2) var(--g-s-4);
		border-bottom: 1px solid var(--g-ink-faint);
		flex-shrink: 0;
	}
	.preset-strip {
		display: flex;
		gap: var(--g-s-2);
		overflow-x: auto;
		scrollbar-width: none;
		padding-bottom: var(--g-s-1);
	}
	.preset-pill {
		white-space: nowrap;
		padding: var(--g-s-1) var(--g-s-3);
		border-radius: 999px;
		border: 1px solid var(--g-ink-faint);
		background: var(--g-paper);
		cursor: pointer;
		font-size: var(--g-text-sm);
		color: var(--g-ink);
	}
	.preset-pill[data-active] {
		background: var(--g-accent);
		color: var(--g-paper);
		border-color: transparent;
	}
	.preset-info {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: var(--g-s-2) var(--g-s-4);
		border-bottom: 1px solid var(--g-ink-faint);
		flex-shrink: 0;
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
	}
	.overlay-scroll {
		flex: 1;
		overflow-y: auto;
		-webkit-overflow-scrolling: touch;
	}
	.accordion-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		padding: var(--g-s-3) var(--g-s-4);
		border: none;
		background: var(--g-surface-1);
		border-bottom: 1px solid var(--g-ink-faint);
		cursor: pointer;
		font-size: var(--g-text-sm);
		font-weight: 600;
		text-align: left;
		color: var(--g-ink);
	}
	.accordion-count {
		font-weight: 400;
		color: var(--g-ink-muted);
		margin-left: var(--g-s-2);
	}
	.metric-row {
		display: flex;
		align-items: center;
		padding: var(--g-s-3) var(--g-s-4);
		border-bottom: 1px solid var(--g-ink-faint);
		gap: var(--g-s-2);
		min-height: 2.75rem;
	}
	.metric-label {
		flex: 1;
		font-size: var(--g-text-md);
		color: var(--g-ink);
	}
	.metric-unit {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		flex-shrink: 0;
	}
	.overlay-footer {
		padding: var(--g-s-3);
		padding-bottom: max(var(--g-s-3), env(safe-area-inset-bottom));
		display: flex;
		gap: var(--g-s-2);
		border-top: 1px solid var(--g-ink-faint);
		background: var(--g-paper);
		flex-shrink: 0;
	}
	:global(.overlay-footer [data-variant="primary"]) {
		flex: 1;
	}
</style>
