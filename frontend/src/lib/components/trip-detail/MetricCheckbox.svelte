<script lang="ts">
	// Epic #138 Issues #174 + #175 — Eine Metric-Zeile mit Custom-Checkbox
	// und Roh/Indikator-Pill-Toggle.
	// Issue #343 — Drei HorizonChips pro Zeile (heute / morgen / uebermorgen);
	//              Mobile-Breakpoint < 600 px stellt Chips in Zeile 2 unter
	//              den Metrik-Namen, eingerueckt auf Namens-Hoehe.
	// Spec: docs/specs/modules/epic_138_174_178_metriken_ui.md §3
	//       docs/specs/modules/issue_343_horizon_chip_ui.md §2
	import { Pill } from '$lib/components/ui/pill/index.js';
	import { HorizonChip } from '$lib/components/ui/horizon-chip/index.js';
	import type { Horizons } from '$lib/types';

	interface MetricEntry {
		id: string;
		label: string;
		unit: string;
		category: string;
		default_enabled: boolean;
		has_friendly_format: boolean;
	}

	interface Props {
		metric: MetricEntry;
		enabled: boolean;
		useIndicator: boolean;
		indicatorCapable: boolean;
		horizons: Horizons;
		onToggle: (id: string, enabled: boolean) => void;
		onModeChange: (id: string, useIndicator: boolean) => void;
		onHorizonChange: (id: string, day: keyof Horizons) => void;
	}

	let {
		metric,
		enabled,
		useIndicator,
		indicatorCapable,
		horizons,
		onToggle,
		onModeChange,
		onHorizonChange,
	}: Props = $props();

	function toggleEnabled() {
		onToggle(metric.id, !enabled);
	}

	function setRaw() {
		onModeChange(metric.id, false);
	}
	function setIndicator() {
		onModeChange(metric.id, true);
	}

	function keyActivate(e: KeyboardEvent, fn: () => void) {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			fn();
		}
	}

	function toggleHorizonToday() { onHorizonChange(metric.id, 'today'); }
	function toggleHorizonTomorrow() { onHorizonChange(metric.id, 'tomorrow'); }
	function toggleHorizonDayAfter() { onHorizonChange(metric.id, 'day_after'); }
</script>

<li class="metric-row" data-slot="metric-row" data-enabled={enabled}>
	<button
		type="button"
		role="checkbox"
		aria-checked={enabled}
		aria-label={metric.label}
		data-testid="weather-metrics-tab-checkbox-{metric.id}"
		onclick={toggleEnabled}
		class="metric-checkbox"
		class:checked={enabled}
	>
		{#if enabled}
			<svg
				class="check-icon"
				viewBox="0 0 16 16"
				fill="none"
				xmlns="http://www.w3.org/2000/svg"
				aria-hidden="true"
			>
				<path
					d="M3 8.5l3.5 3.5L13 5"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
				/>
			</svg>
		{/if}
	</button>
	<span class="metric-name" data-slot="metric-label">{metric.label}</span>
	{#if metric.unit}
		<span class="metric-unit">{metric.unit}</span>
	{/if}
	{#if indicatorCapable}
		<span class="format-toggle">
			<Pill
				tone={!useIndicator ? 'accent' : 'default'}
				data-testid="weather-metrics-tab-format-raw-{metric.id}"
				data-active={String(!useIndicator)}
				class="pill-toggle {!useIndicator ? 'active' : ''}"
				role="button"
				tabindex={0}
				onclick={setRaw}
				onkeydown={(e: KeyboardEvent) => keyActivate(e, setRaw)}
			>Roh</Pill>
			<Pill
				tone={useIndicator ? 'accent' : 'default'}
				data-testid="weather-metrics-tab-format-indicator-{metric.id}"
				data-active={String(useIndicator)}
				class="pill-toggle {useIndicator ? 'active' : ''}"
				role="button"
				tabindex={0}
				onclick={setIndicator}
				onkeydown={(e: KeyboardEvent) => keyActivate(e, setIndicator)}
			>Indikator</Pill>
		</span>
	{/if}
	<span class="horizon-chips" data-slot="horizon-chip-group">
		<HorizonChip
			day="today"
			active={horizons.today}
			onclick={toggleHorizonToday}
			data-testid="horizon-chip-{metric.id}-today"
		/>
		<HorizonChip
			day="tomorrow"
			active={horizons.tomorrow}
			onclick={toggleHorizonTomorrow}
			data-testid="horizon-chip-{metric.id}-tomorrow"
		/>
		<HorizonChip
			day="day_after"
			active={horizons.day_after}
			onclick={toggleHorizonDayAfter}
			data-testid="horizon-chip-{metric.id}-day_after"
		/>
	</span>
</li>

<style>
	.metric-row {
		display: grid;
		grid-template-columns: auto 1fr auto auto auto;
		grid-template-areas: 'check name unit pills chips';
		gap: var(--g-s-3);
		align-items: center;
		padding: var(--g-s-1) 0;
		font-size: var(--g-text-sm);
	}
	.metric-row[data-enabled='false'] .metric-name,
	.metric-row[data-enabled='false'] .metric-unit,
	.metric-row[data-enabled='false'] .format-toggle {
		opacity: 0.6;
	}
	.metric-checkbox {
		grid-area: check;
		flex-shrink: 0;
		width: 1.1rem;
		height: 1.1rem;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0;
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-sm);
		background: var(--g-paper);
		color: var(--g-paper);
		cursor: pointer;
		line-height: 0;
	}
	.metric-checkbox.checked {
		background: var(--g-accent);
		border-color: var(--g-accent);
		color: var(--g-paper);
	}
	.metric-checkbox:focus-visible {
		outline: 2px solid var(--g-accent);
		outline-offset: 1px;
	}
	.check-icon {
		width: 0.85rem;
		height: 0.85rem;
		display: block;
	}
	.metric-name {
		grid-area: name;
		min-width: 0;
	}
	.metric-unit {
		grid-area: unit;
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
		flex-shrink: 0;
	}
	.format-toggle {
		grid-area: pills;
		display: inline-flex;
		gap: var(--g-s-1);
		flex-shrink: 0;
	}
	.format-toggle :global(.pill-toggle) {
		cursor: pointer;
		user-select: none;
	}
	.format-toggle :global(.pill-toggle.active) {
		background: var(--g-accent);
		color: var(--g-paper);
		border-color: var(--g-accent);
	}
	.format-toggle :global(.pill-toggle:focus-visible) {
		outline: 2px solid var(--g-accent);
		outline-offset: 1px;
	}
	.horizon-chips {
		grid-area: chips;
		display: inline-flex;
		gap: var(--g-s-2);
		flex-shrink: 0;
	}
	@media (max-width: 599px) {
		/* Mobile: Chips brechen in Zeile 2 unter den Metrik-Namen,
		   eingerueckt auf Namens-Hoehe (check-Spalte bleibt leer als ".").
		   Roh/Indikator-Pills bleiben in Zeile 1. */
		.metric-row {
			grid-template-columns: auto 1fr auto auto;
			grid-template-areas:
				'check name unit pills'
				'.     chips chips chips';
			row-gap: var(--g-s-2);
		}
		.horizon-chips {
			flex-wrap: wrap;
		}
	}
</style>
