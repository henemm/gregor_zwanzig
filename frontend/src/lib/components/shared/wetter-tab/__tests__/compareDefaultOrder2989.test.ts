// Issue #2989: Standardfolge der Ortsvergleich-Groessen aus dem Backend-Katalog — Zustand GELADEN.
// Spec: docs/specs/modules/refactor_2989_compare_default_order_ssot.md (Tests 5, 6, 8; AC-4, AC-6).
//
// Der Speicher wird ueber den ECHTEN Lader befuellt: `loadCompareMetricCatalog()` verarbeitet die
// echte Endpoint-Antwort (Python `get_compare_metrics`), Netzgrenze ist `globalThis.fetch`.
// Der ungeladene Zustand (Test 5a, Test 7) steht in compareDefaultOrder2989_ungeladen.test.ts.
//
// Erwartete Produktions-Schnittstelle:
//   compareMetricCatalogLoader.ts: getCompareDefaultOrder(): string[] | null, befuellt aus
//     `default_order` der ersten verarbeiteten Katalog-Antwort (im geteilten Promise-Chain).
//   compareMetricOrder.ts: materializeActiveMetricKeys(null) -> Kopie der Standardfolge.
//   ampelSchreiben.ts: vergleichSpeicherPayload rangiert Alt-Schluessel (bisherigeZeilen) ueber
//     die Standardfolge.
//
// RED heute: getCompareDefaultOrder fehlt; die Endpoint-Antwort traegt kein `default_order`.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test src/lib/components/shared/wetter-tab/__tests__/compareDefaultOrder2989.test.ts

import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';

import * as Lader from '../compareMetricCatalogLoader.ts';
import { materializeActiveMetricKeys } from '../../weather-metrics-tab/compareMetricOrder.ts';
import { vergleichSpeicherPayload } from '../ampelSchreiben.ts';
import { BISHERIGE_FOLGE, altvergleichEingabe, endpointAntwort, endpointFetch } from './compareDefaultOrder2989Daten.ts';

const ANTWORT = endpointAntwort();

function standardfolge(): string[] | null {
	assert.equal(typeof Lader.getCompareDefaultOrder, 'function', 'getCompareDefaultOrder() fehlt im Katalog-Lader');
	return Lader.getCompareDefaultOrder();
}

before(async () => {
	const zurueck = endpointFetch();
	try {
		await Lader.loadCompareMetricCatalog();
	} finally {
		zurueck();
	}
});

describe('#2989 Standardfolge geladen', () => {
	test('Test 5: nach dem Laden liefert getCompareDefaultOrder() genau default_order der Antwort', () => {
		assert.ok(Array.isArray(ANTWORT.default_order), 'Endpoint-Antwort ohne default_order');
		assert.deepEqual(standardfolge(), ANTWORT.default_order);
		assert.deepEqual(standardfolge(), BISHERIGE_FOLGE, 'Standardfolge weicht von der bisherigen Mail-Folge ab');
	});

	test('Test 6 (AC-4): materializeActiveMetricKeys(null) = Standardfolge, als Kopie', () => {
		const geladen = standardfolge();
		assert.ok(geladen, 'Standardfolge nicht geladen');
		const a = materializeActiveMetricKeys(null);
		assert.deepEqual(a, BISHERIGE_FOLGE);
		assert.deepEqual(a, geladen);
		a.push('fremd');
		a.reverse();
		assert.deepEqual(standardfolge(), BISHERIGE_FOLGE, 'Mutation des Ergebnisses veraendert den Speicher');
		assert.deepEqual(materializeActiveMetricKeys(null), BISHERIGE_FOLGE, 'zweiter Aufruf liefert mutierte Liste');
		// „bewusst leer" bleibt leer.
		assert.deepEqual(materializeActiveMetricKeys([]), []);
	});

	test('Test 8 (AC-6): Altvergleich nie eingestellt ⇒ active_metrics in bisheriger CV2-Folge', () => {
		assert.ok(standardfolge(), 'Standardfolge nicht geladen');
		const { eingabe, alt } = altvergleichEingabe('uv_index');
		const p = vergleichSpeicherPayload(eingabe);
		const erwartet = BISHERIGE_FOLGE.filter((k) => k !== 'uv_index_max').map((k) => alt[k]);
		assert.ok(erwartet.every(Boolean), 'Alt-Schluessel-Tabelle deckt die Standardfolge nicht ab');
		assert.deepEqual(p.display_config.active_metrics, erwartet);
	});
});
