// Issue #2989: Standardfolge der Ortsvergleich-Groessen aus dem Backend-Katalog — Zustand UNGELADEN.
// Spec: docs/specs/modules/refactor_2989_compare_default_order_ssot.md (Test 5 vorderer Teil, Test 7; AC-5).
//
// Eigene Datei, weil der Speicher modulweit ist und nur einmal befuellt wird: node --test startet
// je Datei einen eigenen Prozess, hier wird der Katalog NIE geladen (kein Abruf).
//
// Erwartete Produktions-Schnittstelle (compareMetricCatalogLoader.ts):
//   getCompareDefaultOrder(): string[] | null   — null, solange keine Katalog-Antwort verarbeitet ist.
// Speicherpfad (ampelSchreiben.ts): vergleichSpeicherPayload schreibt bei ungeladener Standardfolge
// und nie gesetztem `active_metrics` KEIN `active_metrics` (weder Liste noch []).
//
// RED heute: getCompareDefaultOrder fehlt; vergleichSpeicherPayload rangiert ueber die Kopie
// COMPARE_METRIC_KEYS und schreibt `active_metrics`.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test src/lib/components/shared/wetter-tab/__tests__/compareDefaultOrder2989_ungeladen.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import * as Lader from '../compareMetricCatalogLoader.ts';
import { vergleichSpeicherPayload } from '../ampelSchreiben.ts';
import { altvergleichEingabe, endpointFetch } from './compareDefaultOrder2989Daten.ts';

describe('#2989 Standardfolge ungeladen', () => {
	test('Test 5a: vor dem Laden liefert getCompareDefaultOrder() null', () => {
		assert.equal(typeof Lader.getCompareDefaultOrder, 'function', 'getCompareDefaultOrder() fehlt im Katalog-Lader');
		assert.equal(Lader.getCompareDefaultOrder(), null);
	});

	test('Test 7 (AC-5): nie eingestellt + Standardfolge ungeladen ⇒ Payload ohne active_metrics (nicht [])', () => {
		const abrufe: string[] = [];
		const zurueck = endpointFetch(abrufe);
		try {
			const { eingabe } = altvergleichEingabe('uv_index');
			const p = vergleichSpeicherPayload(eingabe);
			assert.deepEqual(abrufe, [], 'Payload-Bau darf den Katalog nicht nachladen');
			assert.ok(
				!('active_metrics' in p.display_config),
				`active_metrics geschrieben, obwohl die Standardfolge fehlt: ${JSON.stringify((p.display_config as Record<string, unknown>).active_metrics)}`
			);
			// Rest der Read-Modify-Write-Nutzlast bleibt vollstaendig.
			assert.ok(p.display_config.ampel, 'ampel fehlt im Payload');
			assert.equal(p.day_window_start_hour, 7);
		} finally {
			zurueck();
		}
	});
});
