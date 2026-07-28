<script lang="ts">
	// Issue #1357 — Eine Auswertungs-Zeile im Inhalt-Reiter: EINZELWAHL ueber die
	// sich ausschliessenden Moeglichkeiten einer Wettergroesse (Spanne / nur
	// Tiefstwert / nur Hoechstwert / nur Mittelwert). PO 2026-07-28: „Es gibt
	// kein zusaetzlich: entweder oder." Die frueheren Haekchen erlaubten
	// Kombinationen, von denen die Kachel nur einen Teil zeigen konnte
	// (Adversary-Befund F001).
	// Bauform: Segmented-Control wie ThresholdMetricRow.svelte in derselben
	// Tabelle — kein neues Bedienmuster.
	// Spec: docs/specs/modules/trip_aggregation_selection.md

	import type { AggregationChoice } from './aggregationSelection.ts';

	interface Props {
		metricId: string;
		label: string;
		choices: AggregationChoice[];
		selectedChoiceId: string | null;
		onSelect: (metricId: string, choiceId: string) => void;
	}

	let { metricId, label, choices, selectedChoiceId, onSelect }: Props = $props();
</script>

<tr data-testid="aggregation-metric-row-{metricId}" data-metric={metricId}>
	<td class="metric-label">{label}</td>
	<td class="segmented-control" data-testid="aggregation-choices-{metricId}">
		{#each choices as c (c.id)}
			<button
				type="button"
				class:active={selectedChoiceId === c.id}
				aria-pressed={selectedChoiceId === c.id}
				onclick={() => onSelect(metricId, c.id)}
				data-testid="aggregation-option-{metricId}-{c.id}"
			>
				{c.label}
			</button>
		{/each}
	</td>
</tr>

<style>
	.metric-label { padding: 8px; font-size: 14px; color: var(--g-ink); }
	.segmented-control { display: flex; gap: 2px; padding: 8px; flex-wrap: wrap; }
	.segmented-control button {
		min-height: 44px; padding: 8px 10px;
		border: 1px solid var(--g-rule, #ddd);
		background: transparent; color: var(--g-ink);
		cursor: pointer; font-size: 14px;
	}
	.segmented-control button.active {
		background: var(--g-accent, #2563eb);
		color: white; border-color: var(--g-accent, #2563eb);
	}
	@media (max-width: 899px) {
		/* Wie ThresholdMetricRow: Zeile bricht auf, Schrift 16px gegen iOS-Zoom. */
		tr { display: block; margin-bottom: 12px; border-bottom: 1px solid var(--g-rule-soft, #eee); }
		td { display: block; }
		.metric-label { font-weight: 600; }
		.segmented-control { width: 100%; padding: 8px 0 0; }
		.segmented-control button { flex: 1; font-size: 16px; }
	}
</style>
