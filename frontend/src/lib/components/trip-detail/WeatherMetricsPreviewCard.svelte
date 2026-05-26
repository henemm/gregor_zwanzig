<script lang="ts">
	// Epic #135 Step 5 — Wetter-Metriken-Preview-Karte fuer die rechte Spalte im
	// Trip-Detail Overview-Tab (Issue #158).
	//
	// Spec: docs/specs/modules/epic_135_step5_right_column.md §3.

	import type { Trip } from '$lib/types';
	import { GCard } from '$lib/components/ui/g-card';
	import { Eyebrow } from '$lib/components/ui/eyebrow';
	import { Pill } from '$lib/components/ui/pill';
	import { getPresetLabel, getActiveMetrics, prettyLabel } from '$lib/utils/rightColumn';

	interface Props {
		trip: Trip;
	}

	let { trip }: Props = $props();

	const presetLabel = $derived(getPresetLabel(trip));
	const metrics = $derived(getActiveMetrics(trip));
</script>

<GCard data-testid="right-card-weather" class="weather-card">
	<Eyebrow>Wetter-Metriken</Eyebrow>
	<h3 data-testid="right-card-weather-preset" class="card-title">{presetLabel}</h3>

	{#if metrics.length === 0}
		<p class="empty-state">Keine Metriken aktiv</p>
	{:else}
		<div class="chips" data-testid="right-card-weather-chips">
			{#each metrics as metric (metric)}
				<Pill tone="default" data-testid="right-card-weather-chip-{metric}" class="chip">
					{prettyLabel(metric)}
				</Pill>
			{/each}
		</div>
	{/if}

	<a href="#weather" data-testid="right-card-weather-edit-link" class="edit-link">
		Bearbeiten →
	</a>
</GCard>

<style>
	:global([data-testid='right-card-weather']) {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 1rem;
		border: 1px solid var(--g-ink-faint);
		border-radius: 0.5rem;
		background: var(--g-surface-1, #fff);
	}
	.card-title {
		font-size: var(--g-text-md);
		font-weight: 600;
		margin: 0;
	}
	.empty-state {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		margin: 0;
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.375rem;
	}
	:global(.chips .chip) {
		display: inline-block;
		padding: 0.125rem 0.5rem;
		border-radius: 9999px;
		background: var(--g-surface-2, rgba(0, 0, 0, 0.05));
		font-size: var(--g-text-xs);
		color: var(--g-ink, inherit);
	}
	.edit-link {
		display: inline-block;
		font-size: var(--g-text-sm);
		color: var(--g-accent-deep);
		text-decoration: none;
		margin-top: 0.25rem;
	}
	.edit-link:hover {
		text-decoration: underline;
	}
</style>
