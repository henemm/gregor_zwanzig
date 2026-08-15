// TDD RED — Issue #1411 (Epic #1372 S4b Scheibe 1) — Mengen-Wahl in der
// Ortsvergleich-Grundauswahl: bei einer Wettergroesse mit mehreren
// Auswertungen (Temperatur, gefuehlte Temperatur) sind Hoechst- und
// Tiefstwert-Kaestchen UNABHAENGIG voneinander an-/abwaehlbar — anders als
// beim Trip (Einzelwahl unter sich ausschliessenden Moeglichkeiten,
// aggregation_selection.test.ts).
//
// Spec: docs/specs/modules/feat_1411_s4b_grundauswahl.md § AC-2, AC-3
// Kontext: docs/context/feat-1411-s4b-grundauswahl.md
//
// Kein Rendering-Harness fuer Svelte-5-Runen im node:test-Setup (Praezedenz:
// aggregation_selection.test.ts). Die Mengen-Wahl-Zeile im Vergleich ruft pro
// Kaestchen unveraendert `toggleCompareMetric(option.key)` ->
// `toggleCompareMetricKeyFromState()` auf (compareMetricOrder.ts, UNVERAENDERT
// — s. Spec § Dependencies) — genau der reihenfolge-erhaltende Toggle, den es
// heute schon fuer die Grundauswahl-Checkbox gibt. Was in RED tatsaechlich
// fehlt, ist NICHT dieser Toggle-Mechanismus (der ist bereits korrekt und
// bleibt es), sondern die Gruppierung, die den Optionen einer Zeile ihre
// einzelnen Katalog-Schluessel gibt (compareAggregationGrouping.ts). Diese
// Tests importieren deshalb bewusst BEIDE Module — die RED-Ursache ist der
// fehlende Import von compareAggregationGrouping.ts, nicht ein Fehler im
// Toggle selbst.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/weather-metrics-tab/__tests__/aggregation_row_multi_select.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';
import { toggleCompareMetricKeyFromState } from '../compareMetricOrder.ts';

const GROUPING_MODULE_FILE = join(
	dirname(fileURLToPath(import.meta.url)),
	'..',
	'compareAggregationGrouping.ts'
);
const GROUPING_MODULE_SPECIFIER = '../compareAggregationGrouping.ts';

// Ausschnitt aus dem echten 26-Zeilen-Katalog (nur die zwei Groessen mit
// mehreren Auswertungen), 1:1 aus get_compare_metric_catalog() gezogen —
// identisch zur Fixture in compareAggregationGrouping.test.ts.
const TEMPERATURE_ROWS = [
	{ metric: 'temp_max_c', label: 'Temperatur', metric_id: 'temperature', aggregation: 'max', aggregation_label: 'Maximum' },
	{ metric: 'temp_min_c', label: 'Temperatur', metric_id: 'temperature', aggregation: 'min', aggregation_label: 'Minimum' },
];
const WIND_CHILL_ROWS = [
	{ metric: 'wind_chill_min_c', label: 'Gefühlte Temperatur', metric_id: 'wind_chill', aggregation: 'min', aggregation_label: 'Minimum' },
	{ metric: 'wind_chill_max_c', label: 'Gefühlte Temperatur', metric_id: 'wind_chill', aggregation: 'max', aggregation_label: 'Maximum' },
];

async function loadGroupingOrFail(): Promise<typeof import('../compareAggregationGrouping.ts') | null> {
	if (!existsSync(GROUPING_MODULE_FILE)) return null;
	try {
		return await import(GROUPING_MODULE_SPECIFIER);
	} catch {
		return null;
	}
}

describe('AC-2: beide Kaestchen einer Gruppe gleichzeitig aktivierbar (keine Exklusivitaet wie beim Trip)', () => {
	test('Hoechstwert an, danach Tiefstwert an -> beide gleichzeitig aktiv', async () => {
		const grouping = await loadGroupingOrFail();
		assert.ok(
			grouping,
			'AC-2 FAIL (RED): compareAggregationGrouping.ts fehlt noch — ohne die Gruppierung gibt es ' +
				'keine Zeile mit mehreren unabhaengigen Kaestchen, an der sich AC-2 pruefen liesse.'
		);
		if (!grouping) return;

		const group = grouping.groupCompareCatalog(TEMPERATURE_ROWS).find((g) => g.metric_id === 'temperature');
		assert.ok(group, 'Temperatur-Gruppe fehlt in der Gruppierung');
		const maxKey = group!.options.find((o) => o.aggregation === 'max')!.key;
		const minKey = group!.options.find((o) => o.aggregation === 'min')!.key;

		let active: string[] = [];
		active = toggleCompareMetricKeyFromState(active, maxKey); // Klick auf "Maximum"
		active = toggleCompareMetricKeyFromState(active, minKey); // Klick auf "Minimum"

		assert.ok(active.includes(maxKey), 'AC-2 FAIL: Maximum wurde durch das Anhaken von Minimum deaktiviert');
		assert.ok(active.includes(minKey), 'AC-2 FAIL: Minimum ist nach dem Anhaken nicht aktiv');
		assert.equal(active.length, 2, 'AC-2 FAIL: es duerfen nicht mehr/weniger als beide Schluessel aktiv sein');
	});
});

describe('AC-3: Abwaehlen des einen Kaestchens wirkt nie auf das andere', () => {
	test('beide aktiv, Tiefstwert abwaehlen -> Hoechstwert bleibt unveraendert aktiv', async () => {
		const grouping = await loadGroupingOrFail();
		assert.ok(
			grouping,
			'AC-3 FAIL (RED): compareAggregationGrouping.ts fehlt noch — ohne die Gruppierung gibt es ' +
				'keine Zeile mit mehreren unabhaengigen Kaestchen, an der sich AC-3 pruefen liesse.'
		);
		if (!grouping) return;

		const group = grouping.groupCompareCatalog(TEMPERATURE_ROWS).find((g) => g.metric_id === 'temperature');
		const maxKey = group!.options.find((o) => o.aggregation === 'max')!.key;
		const minKey = group!.options.find((o) => o.aggregation === 'min')!.key;

		let active = [maxKey, minKey]; // Ausgangszustand: beide aktiv
		active = toggleCompareMetricKeyFromState(active, minKey); // Tiefstwert abwaehlen

		assert.ok(active.includes(maxKey), 'AC-3 FAIL: Hoechstwert wurde durch das Abwaehlen von Tiefstwert mit-deaktiviert');
		assert.ok(!active.includes(minKey), 'AC-3 FAIL: Tiefstwert ist nach dem Abwaehlen noch aktiv');
		assert.equal(active.length, 1);
	});

	test('gefuehlte Temperatur: dieselbe Unabhaengigkeit, unabhaengig von der Katalog-Reihenfolge (min vor max)', async () => {
		const grouping = await loadGroupingOrFail();
		assert.ok(grouping, 'AC-3 FAIL (RED): compareAggregationGrouping.ts fehlt noch.');
		if (!grouping) return;

		const group = grouping.groupCompareCatalog(WIND_CHILL_ROWS).find((g) => g.metric_id === 'wind_chill');
		const maxKey = group!.options.find((o) => o.aggregation === 'max')!.key;
		const minKey = group!.options.find((o) => o.aggregation === 'min')!.key;

		let active = [minKey, maxKey];
		active = toggleCompareMetricKeyFromState(active, maxKey); // Hoechstwert abwaehlen

		assert.ok(active.includes(minKey), 'AC-3 FAIL: Tiefstwert wurde durch das Abwaehlen von Hoechstwert mit-deaktiviert');
		assert.ok(!active.includes(maxKey));
	});
});

