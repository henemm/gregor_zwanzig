<script lang="ts">
	// Issue #364 — zeigt je Kanal primary.length / Budget; Warn-Färbung bei
	// Überschreitung. Budgets aus metricsEditor.CHANNEL_COL_BUDGET (Signal 5,
	// Telegram 7; Uhrzeit nicht mitgezählt — deckt sich mit #360).
	// Design: docs/design/epic_331_output_layout/screen-metrics-editor.jsx
	import { CHANNEL_COL_BUDGET, channelOverflow } from './metricsEditor.ts';

	interface Props {
		count: number;
	}
	let { count }: Props = $props();

	// Nur Kanäle mit endlichem Spalten-Budget > 0 anzeigen (Telegram, Signal).
	const channels = [
		{ id: 'telegram', label: 'Telegram', budget: CHANNEL_COL_BUDGET.telegram },
		{ id: 'signal', label: 'Signal', budget: CHANNEL_COL_BUDGET.signal },
	];
	const overflow = $derived(channelOverflow(count));
</script>

<div class="markers" data-testid="channel-limit-markers">
	<!-- Issue #365 Fresh-Eyes-Politur: Label ordnet die Badges klar der
		"Spalten"-Überschrift zu. -->
	<span class="markers-label mono">Limit</span>
	{#each channels as c}
		<span
			class="marker"
			class:exceeded={overflow[c.id as 'telegram' | 'signal']}
			data-testid="channel-marker-{c.id}"
			title="{c.label}: max {c.budget} Spalten"
		>
			{c.label} {count}/{c.budget}
		</span>
	{/each}
</div>

<style>
	.markers {
		display: flex;
		gap: var(--g-s-1);
		align-items: center;
	}
	.markers-label {
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
		letter-spacing: var(--g-track-caps);
		text-transform: uppercase;
		margin-right: var(--g-s-1);
	}
	.marker {
		padding: var(--g-s-1) var(--g-s-2);
		font-family: var(--g-font-data);
		font-size: var(--g-text-xs);
		letter-spacing: var(--g-track-wide);
		border-radius: var(--g-radius-pill);
		background: var(--g-surface-1);
		color: var(--g-ink-muted);
		font-weight: 600;
		border: 1px solid transparent;
		white-space: nowrap;
	}
	.marker.exceeded {
		background: color-mix(in srgb, var(--g-warning) 15%, transparent);
		color: var(--g-warning);
		border-color: var(--g-warning);
	}
</style>
