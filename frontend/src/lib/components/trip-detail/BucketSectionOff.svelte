<script lang="ts">
	// Issue #364 — "Nicht im Briefing": ausgeklappt nach Kategorie gruppiert,
	// je Metrik "+ Spalte" / "+ Detail". Design-getreu (screen-metrics-editor.jsx).
	import { Eyebrow } from '$lib/components/atoms';
	import * as Card from '$lib/components/ui/card/index.js';
	import type { MetricEntry } from './metricsEditor.ts';
	import { t, tn, locale, type MessageKey } from '$lib/i18n';
	import { metricLabel } from '$lib/i18n/metricLabel';

	// i18n F9: Kategorie-Namen je Sprache (F5-Schluessel), sonst die uebergebene Beschriftung.
	const KATEGORIE: Record<string, MessageKey> = {
		temperature: 'wertebereiche.kategorie.temperature',
		wind: 'wertebereiche.kategorie.wind',
		precipitation: 'wertebereiche.kategorie.precipitation',
		atmosphere: 'wertebereiche.kategorie.atmosphere',
		winter: 'wertebereiche.kategorie.winter'
	};

	interface Props {
		items: string[];
		metricById: Record<string, MetricEntry>;
		shortById: Record<string, string>;
		categoryLabels: Record<string, string>;
		categoryOrder: string[];
		/** Issue #587: wenn true, wird der "+ Detail"-Knopf ausgeblendet. */
		hideDetailButton?: boolean;
		onAdd: (id: string, target: 'primary' | 'secondary') => void;
	}
	let { items, metricById, shortById, categoryLabels, categoryOrder, hideDetailButton = false, onAdd }: Props = $props();

	let open = $state(false);

	// Gruppiert die off-Metriken nach Kategorie, in CATEGORY_ORDER-Reihenfolge.
	const grouped = $derived.by(() => {
		const byCat: Record<string, MetricEntry[]> = {};
		for (const id of items) {
			const m = metricById[id];
			if (!m) continue;
			(byCat[m.category] ??= []).push(m);
		}
		const cats = Object.keys(byCat);
		const ordered = categoryOrder.filter((c) => cats.includes(c)).concat(
			cats.filter((c) => !categoryOrder.includes(c)),
		);
		return ordered.map((cat) => ({ cat, metrics: byCat[cat] }));
	});
</script>

<Card.Root data-testid="bucket-section-off">
	<button
		type="button"
		class="toggle"
		data-testid="bucket-off-toggle"
		onclick={() => (open = !open)}
	>
		<div>
			<Eyebrow>{$t('trip.layout.nicht_im_briefing')}</Eyebrow>
			<div class="title">
				{$tn('trip.layout.weitere_metriken', items.length)} <span class="muted">{$t('trip.layout.nicht_ausgegeben')}</span>
			</div>
		</div>
		<span class="chev">{open ? $t('trip.layout.einklappen') : $t('trip.layout.aufklappen')}</span>
	</button>

	{#if open}
		<div class="body">
			{#each grouped as g}
				<div class="group">
					<div class="group-label mono">{categoryLabels[g.cat] === undefined ? g.cat : KATEGORIE[g.cat] ? $t(KATEGORIE[g.cat]) : categoryLabels[g.cat]}</div>
					<div class="grid">
						{#each g.metrics as m}
							<div class="off-row" data-testid="off-metric-{m.id}">
								<div class="off-label">
									<div class="off-name">{metricLabel(m, $locale)}</div>
									<div class="off-meta mono">{m.unit || '—'} · {shortById[m.id] ?? m.label.slice(0, 5)}</div>
								</div>
								<button type="button" class="text-btn" data-testid="off-add-column-{m.id}" onclick={() => onAdd(m.id, 'primary')}>{$t('trip.layout.plus_spalte')}</button>
								{#if !hideDetailButton}
									<button type="button" class="text-btn" data-testid="off-add-detail-{m.id}" onclick={() => onAdd(m.id, 'secondary')}>{$t('trip.layout.plus_detail')}</button>
								{/if}
							</div>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</Card.Root>

<style>
	.toggle {
		width: 100%;
		padding: var(--g-s-3) var(--g-s-5);
		display: flex;
		justify-content: space-between;
		align-items: center;
		background: transparent;
		border: none;
		cursor: pointer;
		text-align: left;
	}
	.title {
		font-size: var(--g-text-md);
		font-weight: 600;
		margin-top: 2px;
	}
	.muted {
		color: var(--g-ink-muted);
		font-size: var(--g-text-sm);
		font-weight: 400;
	}
	.chev {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
	}
	.body {
		padding: 0 var(--g-s-5) var(--g-s-5);
		border-top: 1px solid var(--g-rule-soft);
	}
	.group {
		margin-top: var(--g-s-4);
	}
	.group-label {
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
		letter-spacing: var(--g-track-caps);
		text-transform: uppercase;
		margin-bottom: var(--g-s-2);
		font-weight: 600;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
		gap: var(--g-s-2);
	}
	.off-row {
		display: flex;
		align-items: center;
		gap: var(--g-s-2);
		padding: var(--g-s-2) var(--g-s-3);
		border: 1px solid var(--g-rule-soft);
		border-radius: var(--g-radius-sm);
		background: var(--g-surface-1);
	}
	.off-label {
		flex: 1;
		min-width: 0;
	}
	.off-name {
		font-size: var(--g-text-sm);
		font-weight: 500;
		color: var(--g-ink-muted);
	}
	.off-meta {
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
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
