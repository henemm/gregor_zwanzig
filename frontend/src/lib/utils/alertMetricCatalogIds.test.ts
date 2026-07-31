// #1401 Scheibe B, Teil 2 — AC-5: Vollstaendigkeits-Nachweis fuer die
// Zuordnung AlertMetric → Metrik-Register-ID.
// Spec: docs/specs/modules/fix_1401b_register_stundenverlauf_alarme.md
//
// Zweck: jede der 14 Alarm-Groessen ist genau einmal eingeordnet — entweder sie
// hat eine Register-Entsprechung (Crosswalk) oder sie ist bewusst als
// registerlos vermerkt (Aenderungs-Metriken). Damit kann kein neuer Eintrag
// still ohne Entscheidung dazukommen.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/utils/alertMetricCatalogIds.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { ALERT_METRIC_LABELS } from './alertMetricLabels.ts';
import {
	ALERT_METRIC_TO_CATALOG_ID,
	NON_CATALOG_ALERT_METRICS
} from './alertMetricCatalogIds.ts';

// Register-IDs aus src/app/metric_catalog.py (label_de-Zeilen zitiert):
//   gust 175 · precipitation 210 · thunder 256 · snowfall_limit 297 · cape 273
//   visibility 384 · humidity 132 · freezing_level 457 · fresh_snow 480
//   temperature 78
const CATALOG_IDS = new Set([
	'gust', 'precipitation', 'thunder', 'snowfall_limit', 'cape',
	'visibility', 'humidity', 'freezing_level', 'fresh_snow', 'temperature'
]);

// Alle AlertMetric-Werte (types.ts) — Quelle fuer den Abdeckungs-Nachweis.
const ALL_ALERT_METRICS = Object.keys(ALERT_METRIC_LABELS);

describe('#1401b AC-5: jede Alarm-Groesse ist genau einmal eingeordnet', () => {
	test('Es gibt 14 Alarm-Groessen (Vakuum-Schutz)', () => {
		assert.equal(ALL_ALERT_METRICS.length, 14);
	});

	test('Genau drei Groessen sind als registerlos vermerkt', () => {
		assert.equal(NON_CATALOG_ALERT_METRICS.size, 3);
		assert.deepEqual(
			[...NON_CATALOG_ALERT_METRICS].sort(),
			['precipitation_change', 'temperature_change', 'wind_change']
		);
	});

	test('Jede nicht-registerlose Groesse hat einen aufloesbaren Crosswalk-Eintrag', () => {
		for (const metric of ALL_ALERT_METRICS) {
			if (NON_CATALOG_ALERT_METRICS.has(metric as never)) continue;
			const catalogId = ALERT_METRIC_TO_CATALOG_ID[metric as never];
			assert.equal(typeof catalogId, 'string', `${metric} hat keinen Crosswalk-Eintrag`);
			assert.ok(
				CATALOG_IDS.has(catalogId as string),
				`${metric} zeigt auf Register-ID "${catalogId}", die es dort nicht gibt`
			);
		}
	});

	test('Registerlose Menge und Crosswalk ergeben zusammen exakt alle 14 — ohne Ueberschneidung', () => {
		const crosswalkKeys = Object.keys(ALERT_METRIC_TO_CATALOG_ID);
		const overlap = crosswalkKeys.filter((k) => NON_CATALOG_ALERT_METRICS.has(k as never));
		assert.deepEqual(overlap, [], 'Groesse ist gleichzeitig registerlos und zugeordnet');
		assert.deepEqual(
			[...new Set([...crosswalkKeys, ...NON_CATALOG_ALERT_METRICS])].sort(),
			[...ALL_ALERT_METRICS].sort()
		);
	});

	test('Kein Crosswalk-Eintrag zeigt auf eine unbekannte Groesse', () => {
		for (const key of Object.keys(ALERT_METRIC_TO_CATALOG_ID)) {
			assert.ok(ALL_ALERT_METRICS.includes(key), `"${key}" ist keine gueltige Alarm-Groesse`);
		}
	});

	// Die beiden Temperatur-Auswertungen zeigen bewusst auf DIESELBE
	// Register-Groesse — Auswertungs-Kollision, geloest im label_de-Text (AC-4).
	test('temperature_min und temperature_max zeigen beide auf "temperature"', () => {
		assert.equal(ALERT_METRIC_TO_CATALOG_ID['temperature_min'], 'temperature');
		assert.equal(ALERT_METRIC_TO_CATALOG_ID['temperature_max'], 'temperature');
	});

	// thunder_level ist NICHT registerlos: es hat die gueltige Entsprechung
	// "thunder". (Deshalb ist DELTA_ONLY_METRICS aus dem Regel-Editor hier
	// bewusst nicht wiederverwendet — dort steht thunder_level fuer den
	// Regel-MODUS, nicht fuer fehlende Register-Herkunft.)
	test('thunder_level gilt als registerfaehig, nicht als registerlos', () => {
		assert.equal(NON_CATALOG_ALERT_METRICS.has('thunder_level'), false);
		assert.equal(ALERT_METRIC_TO_CATALOG_ID['thunder_level'], 'thunder');
	});
});

describe('#1401b AC-5: vereinheitlichte Aenderungs-Beschriftungen', () => {
	// Bisher zeigte die Alarme-Tabelle hier eigene, abweichende Texte
	// ("Temperatursturz" / "Regenänderung") — nach dem Wegfall der lokalen
	// Zweitquelle gilt ueberall dieser eine Wortlaut.
	// #1435 E1a-2 AC-9 (PO-Entscheidung 2026-07-31): dieselbe Eigenschaft
	// (EIN Wortlaut je Aenderungs-Alarm), nachgezogen auf den neuen Stil
	// "Temperatur (Minimum)".
	test('temperature_change heisst "Temperatur (Änderung)"', () => {
		assert.equal(ALERT_METRIC_LABELS['temperature_change'].label_de, 'Temperatur (Änderung)');
	});

	test('precipitation_change heisst "Niederschlag (Änderung)"', () => {
		assert.equal(ALERT_METRIC_LABELS['precipitation_change'].label_de, 'Niederschlag (Änderung)');
	});

	test('wind_change heisst "Wind (Änderung)"', () => {
		assert.equal(ALERT_METRIC_LABELS['wind_change'].label_de, 'Wind (Änderung)');
	});
});
