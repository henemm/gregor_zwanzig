<script lang="ts">
	// Issue #587 — Wetter-Metriken-Tab v2: Abschnitt 2 Grundauswahl.
	// 1:1 nach WM2_Grundauswahl aus screen-trip-edit-v2-weather.jsx.
	// Toggle-Buttons je Kategorie; aktiv = ink-Hintergrund + paper-Text + ✓.
	import type { MetricEntry } from '../../trip-detail/metricsEditor.ts';
	import { CATEGORY_ORDER, CATEGORY_LABELS } from '../../trip-detail/metricsEditor.ts';
	import type { Highlight } from '../../trip-detail/metricsEditor.ts';
	import { t, locale, type MessageKey } from '$lib/i18n';
	import { metricLabel } from '$lib/i18n/metricLabel';

	// Issue #2654 (i18n F5): Kategorie-Ueberschriften ueber den Katalog; unbekannte
	// Kategorie wie bisher (CATEGORY_LABELS bzw. Kennung).
	const KATEGORIE: Record<string, MessageKey> = {
		temperature: 'wertebereiche.kategorie.temperature',
		wind: 'wertebereiche.kategorie.wind',
		precipitation: 'wertebereiche.kategorie.precipitation',
		atmosphere: 'wertebereiche.kategorie.atmosphere',
		winter: 'wertebereiche.kategorie.winter'
	};

	interface Props {
		catalog: Record<string, MetricEntry[]>;
		primaryColumns: string[];
		highlight: Highlight | null;
		onToggle: (id: string, wasOn: boolean) => void;
	}

	let { catalog, primaryColumns, highlight, onToggle }: Props = $props();

	const activeSet = $derived(new Set(primaryColumns));

	function totalActive(): number {
		return primaryColumns.length;
	}
</script>

<div class="grundauswahl" data-testid="wm2-grundauswahl">
	<div class="section-subhead">
		{$t('wertebereiche.grundauswahl.frage')}
		<span class="count">{$t('wertebereiche.grundauswahl.aktiv', { anzahl: totalActive() })}</span>
	</div>
	<div class="categories">
		{#each CATEGORY_ORDER as cat}
			{@const metrics = catalog[cat] ?? []}
			{#if metrics.length > 0}
				<div class="category">
					<div class="cat-label mono">{KATEGORIE[cat] ? $t(KATEGORIE[cat]) : (CATEGORY_LABELS[cat] ?? cat)}</div>
					<div class="toggle-row">
						{#each metrics as m}
							{@const on = activeSet.has(m.id)}
							{@const hl = highlight && highlight.id === m.id}
							<button
								type="button"
								class="toggle-btn"
								class:on
								class:hl
								onclick={() => onToggle(m.id, on)}
								title={metricLabel(m, $locale)}
							>
								{#if on}<span class="check-mark" aria-hidden="true">✓</span>{/if}
								{metricLabel(m, $locale)}
							</button>
						{/each}
					</div>
				</div>
			{/if}
		{/each}
	</div>
	<div class="hint">
		{$t('wertebereiche.grundauswahl.hinweis')}
	</div>
</div>

<style>
	.grundauswahl {
		display: flex;
		flex-direction: column;
		gap: 14px;
	}
	.section-subhead {
		font-size: 15px;
		font-weight: 600;
		color: var(--g-ink);
	}
	.count {
		font-size: 13px;
		font-weight: 400;
		color: var(--g-ink-3);
		margin-left: 8px;
	}
	.categories {
		display: flex;
		flex-direction: column;
		gap: 14px;
	}
	.category {
		display: flex;
		flex-direction: column;
		gap: 7px;
	}
	.cat-label {
		font-size: 11px;
		color: var(--g-ink-3);
		font-weight: 600;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}
	.toggle-row {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}
	.toggle-btn {
		padding: 6px 11px;
		border-radius: 4px;
		cursor: pointer;
		font-size: 12.5px;
		font-weight: 500;
		font-family: inherit;
		border: 1px solid var(--g-rule);
		background: var(--g-card);
		color: var(--g-ink-3);
		transition: background 120ms, color 120ms, border-color 120ms;
		display: inline-flex;
		align-items: center;
		gap: 4px;
	}
	.toggle-btn.on {
		border-color: var(--g-ink);
		background: var(--g-ink);
		color: var(--g-paper);
	}
	.toggle-btn.hl {
		background: var(--g-accent-tint);
		outline: 2px solid var(--g-accent);
		outline-offset: 2px;
	}
	.toggle-btn.on.hl {
		background: var(--g-accent-tint);
		color: var(--g-ink);
		border-color: var(--g-accent);
	}
	.check-mark {
		font-size: 11px;
		opacity: 0.7;
	}
	.hint {
		font-size: 11.5px;
		color: var(--g-ink-4);
		margin-top: 2px;
	}
</style>
