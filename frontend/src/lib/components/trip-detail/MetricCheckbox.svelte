<script lang="ts">
	// Epic #138 Issues #174 + #175 — Eine Metric-Zeile mit Custom-Checkbox
	// und Roh/Indikator-Pill-Toggle.
	// Spec: docs/specs/modules/epic_138_174_178_metriken_ui.md §3
	import { Pill } from '$lib/components/ui/pill/index.js';

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
		onToggle: (id: string, enabled: boolean) => void;
		onModeChange: (id: string, useIndicator: boolean) => void;
	}

	let { metric, enabled, useIndicator, indicatorCapable, onToggle, onModeChange }: Props = $props();

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
</script>

<li class="metric-row">
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
	<span class="metric-name">{metric.label}</span>
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
</li>

<style>
	.metric-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.25rem 0;
		font-size: 0.875rem;
	}
	.metric-checkbox {
		flex-shrink: 0;
		width: 1.1rem;
		height: 1.1rem;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0;
		border: 1px solid var(--g-ink-faint);
		border-radius: 3px;
		background: var(--g-surface, #fff);
		color: var(--g-surface, #fff);
		cursor: pointer;
		line-height: 0;
	}
	.metric-checkbox.checked {
		background: var(--g-accent, #c45a2a);
		border-color: var(--g-accent, #c45a2a);
		color: #fff;
	}
	.metric-checkbox:focus-visible {
		outline: 2px solid var(--g-accent, #c45a2a);
		outline-offset: 1px;
	}
	.check-icon {
		width: 0.85rem;
		height: 0.85rem;
		display: block;
	}
	.metric-name {
		flex: 1;
		min-width: 0;
	}
	.metric-unit {
		font-size: 0.75rem;
		color: var(--g-ink-faint);
		flex-shrink: 0;
	}
	.format-toggle {
		display: inline-flex;
		gap: 0.25rem;
		flex-shrink: 0;
	}
	.format-toggle :global(.pill-toggle) {
		cursor: pointer;
		user-select: none;
	}
	.format-toggle :global(.pill-toggle.active) {
		background: var(--g-accent, #c45a2a);
		color: #fff;
		border-color: var(--g-accent, #c45a2a);
	}
	.format-toggle :global(.pill-toggle:focus-visible) {
		outline: 2px solid var(--g-accent, #c45a2a);
		outline-offset: 1px;
	}
</style>
