// TDD RED — Issue #1401 Scheibe A1, AC-1: die Metrik-Grundauswahl im
// Ortsvergleich zeigt den Namen der Wettergröße und die Auswertung als ZWEI
// getrennte Werte — nicht als einen zusammengesetzten String ("Temperatur max").
// Geprüft wird die Naht, aus der die Auswahl-Einträge entstehen:
// `toCompareSelectionEntries()`. Sie reicht heute `metric_id`/`aggregation`
// durch (#1373), aber nicht `aggregation_label` — deshalb heute ROT.
//
// Spec: docs/specs/modules/fix_1401_a1_namensregister.md § AC-1, Punkt 4/5
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/weather-metrics-tab/__tests__/weatherMetricsTabVergleichLabels.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

const MODULE_SPECIFIER = '../compareMetricSelection.ts';

// Beispielantwort von GET /api/compare/metrics NACH #1401: `label` kommt aus
// dem zentralen Register (ohne Auswertung im Namen), `aggregation_label` ist
// das neue, daneben anzuzeigende Element.
const CATALOG_AFTER_1401 = {
	metrics: [
		{ key: 'temp_max_c', label: 'Temperatur', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -20, rangeMax: 45, step: 1, metric_id: 'temperature', aggregation: 'max', aggregation_label: 'Maximum' },
		{ key: 'temp_min_c', label: 'Temperatur', unit: '°C', decimals: 0, higherIsBetter: true, kind: 'range', rangeMin: -30, rangeMax: 30, step: 1, metric_id: 'temperature', aggregation: 'min', aggregation_label: 'Minimum' },
		{ key: 'wind_max_kmh', label: 'Wind', unit: 'km/h', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, metric_id: 'wind', aggregation: 'max', aggregation_label: 'Maximum' },
		{ key: 'sunny_hours_h', label: 'Sonnenstunden', unit: 'h', decimals: 1, higherIsBetter: true, kind: 'range', rangeMin: 0, rangeMax: 12, step: 0.5, metric_id: 'sunshine', aggregation: 'sum', aggregation_label: 'Summe' },
		{ key: 'cloud_avg_pct', label: 'Bewölkung', unit: '%', decimals: 0, higherIsBetter: false, kind: 'range', rangeMin: 0, rangeMax: 100, step: 5, metric_id: 'cloud_total', aggregation: 'avg', aggregation_label: 'Mittel' }
	]
};

type SelectionEntryWithLabels = {
	metric: string;
	label: string;
	aggregation?: string;
	aggregation_label?: string;
};

async function selectionEntries(response: unknown): Promise<SelectionEntryWithLabels[]> {
	const mod: typeof import('../compareMetricSelection.ts') = await import(MODULE_SPECIFIER);
	return mod.toCompareSelectionEntries(
		response as Parameters<typeof mod.toCompareSelectionEntries>[0]
	) as unknown as SelectionEntryWithLabels[];
}

describe('#1401 AC-1: Name und Auswertung sind zwei getrennte Werte', () => {
	test('jeder Auswahl-Eintrag traegt aggregation_label neben dem Namen', async () => {
		const result = await selectionEntries(CATALOG_AFTER_1401);
		assert.equal(result.length, 5, `erwartet 5 Eintraege, erhalten ${result.length}`);
		CATALOG_AFTER_1401.metrics.forEach((expected, i) => {
			assert.equal(result[i]?.label, expected.label, `AC-1 FAIL: Name an Index ${i}`);
			assert.equal(
				result[i]?.aggregation_label,
				expected.aggregation_label,
				`AC-1 FAIL: aggregation_label an Index ${i} nicht durchgereicht — erwartet ` +
					`'${expected.aggregation_label}', erhalten '${result[i]?.aggregation_label}'. ` +
					'Ohne dieses Feld kann die Grundauswahl die Auswertung nicht als eigenes ' +
					'Element neben dem Namen zeigen.'
			);
		});
	});

	test('der Name enthaelt die Auswertung nicht (kein zusammengesetzter String)', async () => {
		const result = await selectionEntries(CATALOG_AFTER_1401);
		for (const entry of result) {
			for (const wort of ['Maximum', 'Minimum', 'Mittel', 'Summe', ' max', ' min', ' Ø']) {
				assert.ok(
					!entry.label.endsWith(wort),
					`AC-1 FAIL: '${entry.label}' (${entry.metric}) traegt die Auswertung im Namen`
				);
			}
		}
	});

	test('gleiche Groesse, verschiedene Auswertung: gleicher Name, unterscheidbares Element', async () => {
		const result = await selectionEntries(CATALOG_AFTER_1401);
		const hi = result.find((e) => e.metric === 'temp_max_c');
		const lo = result.find((e) => e.metric === 'temp_min_c');
		assert.ok(hi && lo, 'AC-1 FAIL: beide Temperatur-Eintraege muessen erhalten bleiben');
		assert.equal(hi?.label, lo?.label, 'AC-1 FAIL: beide sollen denselben Namen tragen');
		assert.equal(hi?.aggregation_label, 'Maximum');
		assert.equal(lo?.aggregation_label, 'Minimum');
		assert.notEqual(
			hi?.aggregation_label,
			lo?.aggregation_label,
			'AC-1 FAIL: die beiden Zeilen waeren in der Liste ununterscheidbar'
		);
	});

	test('Eintrag ohne aggregation_label erfindet keinen leeren Schluessel', async () => {
		// Vertrag aus #1350/#1373: fehlt das Feld in der Antwort, darf das
		// Mapping es NICHT als `undefined` ergaenzen (strikter deepEqual).
		const result = await selectionEntries({
			metrics: [{ key: 'ohne_auswertung', label: 'Ohne Auswertung' }]
		});
		assert.deepEqual(result, [{ metric: 'ohne_auswertung', label: 'Ohne Auswertung' }]);
	});
});
