<script lang="ts">
	// Issue #173 — PresetRow: klickbare Zeile im Metriken-Editor, ersetzt das
	// vormalige Template-Dropdown. Single Source of Truth fuer Aktiv-Status ist
	// `selectedTemplate` aus WeatherMetricsTab (basiert auf display_config.preset_name).
	interface Props {
		id: string;
		label: string;
		metricCount: number;
		isActive: boolean;
		onSelect: (id: string) => void;
	}
	let { id, label, metricCount, isActive, onSelect }: Props = $props();
</script>

<button
	class="preset-row"
	class:active={isActive}
	type="button"
	data-testid="weather-metrics-preset-row-{id}"
	onclick={() => onSelect(id)}
>
	<!-- Name-Span trägt KEINEN prefixed testid mehr, weil strict-mode-Filter
		 [data-testid^="weather-metrics-preset-row-"] mit hasText sonst sowohl
		 den Button als auch den Name-Span findet. Siehe epic-138-block-b AC-6d. -->
	<span class="preset-name" data-testid="preset-row-name-{id}">{label}</span>
	<span class="preset-count" data-testid="weather-metrics-preset-row-{id}-count">{metricCount} Metriken</span>
	<span class="preset-badge" data-testid="weather-metrics-preset-row-{id}-badge">Standard</span>
</button>

<style>
	.preset-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		width: 100%;
		padding: 0.6rem 1rem;
		border: 1px solid var(--g-ink-faint);
		border-radius: 4px;
		cursor: pointer;
		background: var(--g-surface-0);
		font: inherit;
		color: inherit;
		text-align: left;
	}
	.preset-row.active {
		border-color: var(--g-accent, #c45a2a);
		background-color: color-mix(in srgb, var(--g-accent, #c45a2a) 8%, var(--g-surface-0));
	}
	.preset-name {
		flex: 1;
		font-weight: 500;
	}
	.preset-count {
		font-size: 0.875rem;
		color: var(--g-ink-muted);
		flex-shrink: 0;
	}
	.preset-badge {
		font-size: 0.75rem;
		padding: 0.1rem 0.4rem;
		border: 1px solid var(--g-ink-faint);
		border-radius: 3px;
		color: var(--g-ink-muted);
		flex-shrink: 0;
	}
</style>
