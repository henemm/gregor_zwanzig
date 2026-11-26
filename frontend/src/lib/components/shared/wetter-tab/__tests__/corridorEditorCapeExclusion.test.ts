// TDD RED — Issue #1585 (Spec: docs/specs/modules/feat_1585_cape_selectable_false.md,
// AC-4 Frontend-Haelfte).
//
// CAPE ist fachlich nur eine Zutat der Gewitterstufen-Fusion, keine waehlbare
// Wettergroesse (PO-Regel 2026-08-10, Muster ADR-0005/#710). Der Backend-Katalog
// liefert `cape_max_jkg` ab #1585 nicht mehr aus — die zwei hartkodierten
// Frontend-Fundstellen in corridorEditorState.ts muessen mitziehen, sonst
// behandelt ein Alt-Vergleich mit `active_metrics=null` CAPE weiterhin als
// aktiv. Seit #2989 ist die Fallback-Liste die Standardfolge `default_order` der
// Katalog-Antwort; sie wird hier ueber den echten Lader befuellt (fetch-Stub an
// der Netzgrenze, echte Endpoint-Antwort).
//
// Ausfuehrung: cd frontend && npm test -- \
//   src/lib/components/shared/corridor-editor/__tests__/corridorEditorCapeExclusion.test.ts

import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';

import { _COMPARE_DEFAULTS } from '../corridorEditorState.ts';
import { getCompareDefaultOrder, loadCompareMetricCatalog } from '../compareMetricCatalogLoader.ts';
import { endpointFetch } from './compareDefaultOrder2989Daten.ts';

const CAPE_KEY = 'cape_max_jkg';
let standardfolge: string[] = [];

before(async () => {
	const zurueck = endpointFetch();
	try {
		await loadCompareMetricCatalog();
	} finally {
		zurueck();
	}
	standardfolge = getCompareDefaultOrder() ?? [];
	assert.ok(standardfolge.length > 0, 'Standardfolge nicht geladen');
});

describe('AC-4 (Frontend): cape_max_jkg ist keine waehlbare Vergleichs-Groesse mehr', () => {
	test('die Standardfolge (default_order) fuehrt cape_max_jkg nicht', () => {
		assert.equal(
			standardfolge.includes(CAPE_KEY),
			false,
			`AC-4 FAIL: die Standardfolge enthaelt noch ${CAPE_KEY} — ein Alt-Vergleich ` +
				'ohne gespeicherte active_metrics wuerde CAPE weiterhin als aktive Metrik ' +
				`fuehren. Liste: ${standardfolge.join(', ')}`
		);
	});

	test('_COMPARE_DEFAULTS fuehrt cape_max_jkg nicht mehr', () => {
		assert.equal(
			Object.keys(_COMPARE_DEFAULTS).includes(CAPE_KEY),
			false,
			`AC-4 FAIL: _COMPARE_DEFAULTS enthaelt noch ${CAPE_KEY} — der Startwert fuer ` +
				'"+ Metrik hinzufuegen" verweist auf eine Groesse, die der Katalog nicht ' +
				'mehr anbietet.'
		);
	});

	test('die uebrigen Vergleichs-Groessen bleiben unveraendert erhalten', () => {
		// Kein Kollateralschaden: die beiden Nachbarn aus derselben #1296-Klasse
		// (freezing_level_m) und der Gewitter-Eintrag selbst bleiben waehlbar —
		// entfernt wird ausschliesslich CAPE.
		for (const key of ['freezing_level_m', 'thunder_level_max', 'temp_max_c']) {
			assert.ok(
				standardfolge.includes(key),
				`AC-4 FAIL: ${key} ist mit CAPE zusammen aus der Standardfolge verschwunden`
			);
		}
		assert.ok(
			Object.keys(_COMPARE_DEFAULTS).includes('freezing_level_m'),
			'AC-4 FAIL: freezing_level_m ist mit CAPE zusammen aus _COMPARE_DEFAULTS verschwunden'
		);
	});
});
