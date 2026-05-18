<script lang="ts">
	// Epic #138 Issues #174 + #175 — Eine Metric-Zeile mit Custom-Checkbox
	// und Roh/Indikator-Pill-Toggle.
	// Spec: docs/specs/modules/epic_138_174_178_metriken_ui.md §3

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
	<input
		type="checkbox"
		data-testid="weather-metrics-tab-checkbox-{metric.id}"
		checked={enabled}
		onchange={toggleEnabled}
		class="metric-checkbox"
		aria-label={metric.label}
	/>
	<span class="metric-name">{metric.label}</span>
	{#if metric.unit}
		<span class="metric-unit">{metric.unit}</span>
	{/if}
	{#if indicatorCapable}
		<span class="format-toggle">
			<span
				data-slot="pill"
				data-tone={!useIndicator ? 'accent' : 'default'}
				data-testid="weather-metrics-tab-format-raw-{metric.id}"
				data-active={String(!useIndicator)}
				class="pill-toggle"
				class:active={!useIndicator}
				role="button"
				tabindex="0"
				onclick={setRaw}
				onkeydown={(e) => keyActivate(e, setRaw)}
			>Roh</span>
			<span
				data-slot="pill"
				data-tone={useIndicator ? 'accent' : 'default'}
				data-testid="weather-metrics-tab-format-indicator-{metric.id}"
				data-active={String(useIndicator)}
				class="pill-toggle"
				class:active={useIndicator}
				role="button"
				tabindex="0"
				onclick={setIndicator}
				onkeydown={(e) => keyActivate(e, setIndicator)}
			>Indikator</span>
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
	}
	.metric-name {
		flex: 1;
		min-width: 0;
	}
	.metric-unit {
		font-size: 0.75rem;
		color: var(--g-ink-faint, #888);
		flex-shrink: 0;
	}
	.format-toggle {
		display: inline-flex;
		gap: 0.25rem;
		flex-shrink: 0;
	}
	.pill-toggle {
		display: inline-flex;
		align-items: center;
		padding: 0.15rem 0.55rem;
		font-size: 0.7rem;
		border-radius: 999px;
		border: 1px solid var(--g-border, #ddd);
		background: var(--g-surface, #fff);
		color: var(--g-ink-faint, #888);
		cursor: pointer;
		line-height: 1.2;
		user-select: none;
	}
	.pill-toggle.active {
		background: var(--g-accent, #c45a2a);
		color: #fff;
		border-color: var(--g-accent, #c45a2a);
	}
	.pill-toggle:focus-visible {
		outline: 2px solid var(--g-accent, #c45a2a);
		outline-offset: 1px;
	}
</style>
