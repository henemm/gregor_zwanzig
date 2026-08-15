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
	//
	// Issue #1411 (Epic #1372 S4b Scheibe 1): `mode='multiple'` ergaenzt die
	// Ortsvergleich-Mengen-Wahl (Hoechst-/Tiefstwert unabhaengig ankreuzbar)
	// als zweiten Modus desselben geteilten Bausteins statt einer
	// Compare-Zweitkomponente (Trip/Compare-Teilungs-Invariante).
	// Spec: docs/specs/modules/feat_1411_s4b_grundauswahl.md § Implementation
	// Details 2, AC-2, AC-3
	//
	// Issue #1728 Scheibe 3: der Trip-Modus `mode='single'` (Einzelwahl ueber
	// `MetricConfig.aggregations`) ist ersatzlos entfallen — das Feld ist
	// abgeschafft. `mode` bleibt als Prop bestehen, weil beide Aufrufer es
	// ausdruecklich mit `"multiple"` setzen; die Kaestchen-Form ist seither die
	// einzige.
	//
	// Issue #1406 Scheibe A (Epic #1372 S4b Scheibe 2): optionaler
	// `testidPrefix` — der Ausblick wird der zweite `mode='multiple'`-Aufrufer
	// (neben der Uebersicht) auf derselben Editor-Seite; ohne Praefix wuerden
	// beide dieselben `data-testid`s tragen. Ohne Angabe bleiben Zeilen- und
	// Kaestchen-Testid bitidentisch zu vorher (Uebersicht ruft ohne Praefix
	// auf). Spec: docs/specs/modules/feat_1406a_ausblick_geteiltes_element.md
	// § Implementation Details 2, AC-8

	import type { CompareAggregationOption } from './compareAggregationGrouping.ts';

	interface Props {
		metricId: string;
		label: string;
		mode?: 'multiple';
		// Die rohen Katalog-Optionen einer Gruppe, jede unabhaengig
		// an-/abwaehlbar; `onToggle` bekommt den jeweiligen einzelnen
		// Katalog-`key` (derselbe Toggle-Pfad wie heute).
		options?: CompareAggregationOption[];
		selectedChoiceIds?: string[];
		onToggle?: (metricId: string, key: string) => void;
		// Ohne Angabe: heutige Testids unveraendert (Uebersicht, #1411-Default).
		testidPrefix?: string;
	}

	let {
		metricId, label,
		options = [], selectedChoiceIds = [], onToggle,
		testidPrefix
	}: Props = $props();
</script>

<tr
	data-testid={testidPrefix ? `${testidPrefix}-metric-row-${metricId}` : `aggregation-metric-row-${metricId}`}
	data-metric={metricId}
>
	<td class="metric-label">{label}</td>
	<td
		class="segmented-control"
		data-testid={testidPrefix ? `${testidPrefix}-choices-${metricId}` : `aggregation-choices-${metricId}`}
	>
		{#each options as o (o.key)}
			<label
				class="multi-option"
				data-testid={testidPrefix ? `${testidPrefix}-option-${metricId}-${o.aggregation}` : `weather-metrics-vergleich-option-${metricId}-${o.aggregation}`}
			>
				<input
					type="checkbox"
					checked={selectedChoiceIds.includes(o.key)}
					onchange={() => onToggle?.(metricId, o.key)}
					data-metric-key={o.key}
				/>
				<span>{o.aggregation_label}</span>
			</label>
		{/each}
	</td>
</tr>

<style>
	.metric-label { padding: 8px; font-size: 14px; color: var(--g-ink); }
	.segmented-control { display: flex; gap: 2px; padding: 8px; flex-wrap: wrap; }
	/* Issue #1411: unabhaengige Kaestchen; seit #1728 S3 die einzige Form. */
	.multi-option {
		display: inline-flex; align-items: center; gap: 6px;
		min-height: 44px; padding: 8px 10px;
		cursor: pointer; font-size: 14px; color: var(--g-ink);
	}
	@media (max-width: 899px) {
		/* Wie ThresholdMetricRow: Zeile bricht auf, Schrift 16px gegen iOS-Zoom. */
		tr { display: block; margin-bottom: 12px; border-bottom: 1px solid var(--g-rule-soft, #eee); }
		td { display: block; }
		.metric-label { font-weight: 600; }
		.segmented-control { width: 100%; padding: 8px 0 0; }
		.multi-option { font-size: 16px; }
	}
</style>
