<script lang="ts">
	// Epic #138 Issue #174 — Strukturierte Kategorie-Gruppe für WeatherMetricsTab.
	// Spec: docs/specs/modules/epic_138_174_178_metriken_ui.md §2
	import type { Snippet } from 'svelte';
	import { Eyebrow } from '$lib/components/ui/eyebrow/index.js';

	interface Props {
		slug: string;
		label: string;
		activeCount: number;
		totalCount: number;
		children: Snippet;
	}

	let { slug, label, activeCount, totalCount, children }: Props = $props();
</script>

<section data-testid="metric-group-{slug}" class="metric-group">
	<div class="metric-group-header">
		<Eyebrow>{label}</Eyebrow>
		<span
			data-testid="metric-group-counter"
			class="metric-group-counter"
			data-active={activeCount > 0 ? 'true' : 'false'}
		>
			{activeCount} / {totalCount}
		</span>
	</div>
	<ul class="metric-group-list">
		{@render children()}
	</ul>
</section>

<style>
	.metric-group {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.metric-group-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.metric-group-counter {
		font-size: 0.75rem;
		color: var(--g-ink-faint);
		font-variant-numeric: tabular-nums;
	}
	.metric-group-counter[data-active='true'] {
		color: var(--g-accent, #c45a2a);
		font-weight: 600;
	}
	.metric-group-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
</style>
