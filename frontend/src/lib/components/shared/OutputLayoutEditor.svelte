<script lang="ts">
	// Issue #431 — Trip-agnostischer Output-Layout-Editor.
	// Wird wiederverwendet von:
	//   - Trip-Detail-Tab: WeatherMetricsTab.svelte (channel="email" fix)
	//   - Trip-Wizard:     Step4Layout.svelte (4 Channel-Tabs)
	//
	// KEINE API-Calls — Catalog/Presets kommen ueber Props.
	// KEINE trip-Prop — Editor ist trip-agnostisch.
	//
	// SMS-Sonderzweig: statt Bucket-Editor eine flache priorisierte Liste mit
	// 140-Zeichen-Budget-Anzeige (Spec §6 / AC-9).
	// Issue #1272: die SMS-Liste ist jetzt ziehbar (geteilter Baustein
	// `shared/dnd/SortableList`), die ▲/▼-Buttons sind ersatzlos entfallen —
	// ihre Funktion übernimmt der Tastatur-Pfad auf dem Griff (ADR-0024).
	import { Btn, Card, Eyebrow } from '$lib/components/atoms';
	import SortableList from '$lib/components/shared/dnd/SortableList.svelte';
	import DragHandle from '$lib/components/shared/dnd/DragHandle.svelte';
	import BucketSection from '$lib/components/trip-detail/BucketSection.svelte';
	import BucketSectionOff from '$lib/components/trip-detail/BucketSectionOff.svelte';
	import PresetRow from '$lib/components/trip-detail/PresetRow.svelte';
	import {
		CATEGORY_LABELS,
		CATEGORY_ORDER,
		indicatorCapable,
		type Buckets,
		type MetricCatalog,
		type MetricEntry,
	} from '$lib/components/trip-detail/metricsEditor';
	import type { MetricPreset } from '$lib/types';

	interface Template {
		id: string;
		label: string;
		metrics: string[];
	}

	interface Props {
		catalog: MetricCatalog;
		buckets: Buckets;
		friendlyMap: Record<string, boolean>;
		selectedTemplate?: string;
		channel: 'email' | 'telegram' | 'sms';
		templates?: Template[];
		userPresets?: MetricPreset[];
		// Optional: Caller darf eigene Labels durchreichen (Pre-existing #392 test
		// erwartet, dass WeatherMetricsTab `categoryLabels={CATEGORY_LABELS}` setzt).
		// Default = importierte CATEGORY_LABELS aus metricsEditor.ts.
		categoryLabels?: Record<string, string>;
		/**
		 * Issue #587: Wenn true, wird der secondary-Abschnitt ("Detail-Werte")
		 * komplett ausgeblendet und "→ Detail"-Knöpfe entfernt. Alle aktiven
		 * Metriken sind genau eine Spaltenliste. Default false → Wizard/Compare
		 * bleiben unverändert.
		 */
		hideDetailBucket?: boolean;
		onMove?: (id: string, target: 'primary' | 'secondary' | 'off') => void;
		onMode?: (id: string, useIndicator: boolean) => void;
		onSelectPreset?: (id: string) => void;
		onDndReorder?: (bucket: 'primary' | 'secondary', newOrder: string[]) => void;
	}

	let {
		catalog,
		buckets = $bindable(),
		friendlyMap = $bindable(),
		selectedTemplate = $bindable(''),
		channel,
		templates = [],
		userPresets = [],
		categoryLabels = CATEGORY_LABELS,
		hideDetailBucket = false,
		onMove,
		onMode,
		onSelectPreset,
		onDndReorder,
	}: Props = $props();

	// Abgeleitete Lookup-Maps (Katalog -> Metrik-Entry und Kuerzel).
	const metricById = $derived.by(() => {
		const map: Record<string, MetricEntry> = {};
		for (const ms of Object.values(catalog)) for (const m of ms) map[m.id] = m;
		return map;
	});

	const shortById = $derived.by(() => {
		const map: Record<string, string> = {};
		for (const id of Object.keys(metricById)) {
			const label = metricById[id].label;
			map[id] = label.length > 6 ? label.slice(0, 6) : label;
		}
		return map;
	});

	// Issue #431 — Benannte Handler statt anonymer Closures (Safari/Factory-Pattern).
	function handleSmsDndReorder(newOrder: string[]) {
		onDndReorder?.('primary', newOrder);
	}
	function smsItemLabel(id: string, i: number) {
		return `${i + 1}. ${metricById[id]?.label ?? id}`;
	}
	function handleRemove(id: string) {
		onMove?.(id, 'off');
	}
	function handlePresetSelect(id: string) {
		onSelectPreset?.(id);
	}

	// SMS: grobe 140-Zeichen-Budget-Anzeige (Layout-Heuristik, KEIN Render).
	// Annahme: ~12 Zeichen pro Metrik im SMS-Format ("Temp 11.6 ").
	const smsBudgetUsed = $derived(buckets.primary.length * 12);
	const smsBudgetTotal = 140;
	const smsOverBudget = $derived(smsBudgetUsed > smsBudgetTotal);
</script>

{#if channel === 'sms'}
	<!-- SMS-Sonderzweig: flache priorisierte Liste, kein Bucket-Editor -->
	<div data-testid="output-layout-editor-sms" class="sms-editor">
		<Card>
			<div class="head">
				<Eyebrow>SMS · Priorisierte Liste</Eyebrow>
				<div class="title">Reihenfolge</div>
				<p class="hint">
					SMS hat maximal 140 Zeichen. Reihenfolge: oben = wichtiger. Was nicht
					mehr in das Budget passt, wird automatisch weggelassen.
				</p>
			</div>

			<!-- Budget-Anzeige -->
			<div
				class="budget-bar"
				data-testid="sms-budget-display"
				class:exceeded={smsOverBudget}
			>
				<span class="budget-label mono">Zeichen</span>
				<span class="budget-value mono">{smsBudgetUsed} / {smsBudgetTotal}</span>
			</div>

			{#if buckets.primary.length === 0}
				<div class="empty">Keine Metriken — aus „Nicht im Briefing" hinzufügen.</div>
			{:else}
				<SortableList
					items={buckets.primary}
					onDndReorder={handleSmsDndReorder}
					ariaLabel="SMS-Metriken, Reihenfolge"
					itemLabel={smsItemLabel}
				>
					{#snippet row(id: string, i: number)}
						{@const metric = metricById[id]}
						{#if metric}
							<div class="sms-row" data-testid={`sms-row-${id}`} data-metric-id={id}>
								<DragHandle />
								<span class="rank mono">{i + 1}.</span>
								<span class="name">{metric.label}</span>
								<div class="row-actions">
									<Btn
										variant="ghost"
										size="icon-sm"
										onclick={() => handleRemove(id)}
										aria-label="Entfernen"
									>
										×
									</Btn>
								</div>
							</div>
						{/if}
					{/snippet}
				</SortableList>
			{/if}
		</Card>

		<BucketSectionOff
			items={buckets.off}
			{metricById}
			{shortById}
			{categoryLabels}
			categoryOrder={[...CATEGORY_ORDER]}
			onAdd={(id) => onMove?.(id, 'primary')}
		/>
	</div>
{:else}
	<!-- Standard-Mode: Bucket-Editor (Email/Telegram/SMS) -->
	<div data-testid="output-layout-editor-standard" class="standard-editor">
		{#if userPresets.length > 0 || templates.length > 0}
			<div class="preset-list" data-testid="output-layout-preset-list">
				<Eyebrow>Preset-Auswahl</Eyebrow>
				{#each userPresets as p (p.id)}
					<PresetRow
						id={p.id}
						label={p.name}
						metricCount={p.metrics.length}
						isActive={selectedTemplate === p.id}
						onSelect={handlePresetSelect}
					/>
				{/each}
				{#each templates as t (t.id)}
					<PresetRow
						id={t.id}
						label={t.label}
						metricCount={t.metrics.length}
						isActive={selectedTemplate === t.id}
						onSelect={handlePresetSelect}
					/>
				{/each}
			</div>
		{/if}

		<BucketSection
			eyebrow="Im Briefing als Spalte"
			title="Spalten"
			hint="Eine eigene Tabellen-Spalte je Metrik. Reihenfolge = von links nach rechts."
			bucket="primary"
			items={buckets.primary}
			{metricById}
			{shortById}
			{friendlyMap}
			{indicatorCapable}
			showLimitMarkers
			hideDetailButton={hideDetailBucket}
			onMode={(id, useIndicator) => onMode?.(id, useIndicator)}
			onMove={(id, target) => onMove?.(id, target)}
			onDndReorder={(newOrder) => onDndReorder?.('primary', newOrder)}
		/>

		{#if !hideDetailBucket}
			<BucketSection
				eyebrow="Im Briefing als Detail"
				title="Detail-Werte"
				hint="Erscheinen als kompakte Zeile direkt unter der Tabelle."
				bucket="secondary"
				items={buckets.secondary}
				{metricById}
				{shortById}
				{friendlyMap}
				{indicatorCapable}
				onMode={(id, useIndicator) => onMode?.(id, useIndicator)}
				onMove={(id, target) => onMove?.(id, target)}
					onDndReorder={(newOrder) => onDndReorder?.('secondary', newOrder)}
			/>
		{/if}

		<BucketSectionOff
			items={buckets.off}
			{metricById}
			{shortById}
			{categoryLabels}
			categoryOrder={[...CATEGORY_ORDER]}
			hideDetailButton={hideDetailBucket}
			onAdd={(id, target) => onMove?.(id, target)}
		/>
	</div>
{/if}

<style>
	.standard-editor,
	.sms-editor {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-4);
	}
	.preset-list {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-1);
	}
	.head {
		padding: var(--g-s-4) var(--g-s-5) var(--g-s-3);
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.title {
		font-size: var(--g-text-xl);
		font-weight: 600;
		margin-top: 2px;
		letter-spacing: var(--g-track-tight);
	}
	.hint {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		margin-top: var(--g-s-2);
		line-height: 1.5;
		max-width: 760px;
	}
	.budget-bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: var(--g-s-2) var(--g-s-5);
		background: var(--g-surface-1);
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.budget-label,
	.budget-value {
		font-family: var(--g-font-data);
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
		letter-spacing: var(--g-track-caps);
		text-transform: uppercase;
	}
	.budget-bar.exceeded .budget-value {
		color: var(--g-warning);
		font-weight: 600;
	}
	.empty {
		padding: var(--g-s-5);
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		font-style: italic;
		text-align: center;
	}
	.sms-row {
		display: grid;
		grid-template-columns: auto auto 1fr auto;
		align-items: center;
		gap: var(--g-s-3);
		padding: var(--g-s-3) var(--g-s-5);
		border-bottom: 1px solid var(--g-rule-soft);
	}
	/* #1272: die Zeile sitzt jetzt in einem Item-Wrapper von SortableList —
	   :last-child griffe auf den Wrapper, nicht mehr auf die Zeile. */
	:global(.sortable-item:last-child) .sms-row {
		border-bottom: none;
	}
	.rank {
		font-family: var(--g-font-data);
		color: var(--g-ink-muted);
		font-size: var(--g-text-sm);
	}
	.name {
		font-size: var(--g-text-sm);
		color: var(--g-ink);
	}
	.row-actions {
		display: flex;
		gap: var(--g-s-1);
	}
</style>
