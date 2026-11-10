// Issue #2881 Lieferung B — Melde-Regel der Segment-Felder (DatumFeld/UhrzeitFeld):
// Zwischenstände unfertiger Segmente gehen nie nach außen (auch nicht nach einer Pause, Fix-Loop
// F-B1), fertige Segmente und Kalender-/Programm-Wahl sofort, beim Verlassen der offene Wert;
// ein fremder Wertwechsel verwirft Offenes und sperrt bis zur Freigabe (Fix-Loop 2). Echte Klasse.
// Die Wirkstelle im Browser prüft design-system-trip-vergleich.spec.ts (DS-2).
// Spec: docs/specs/modules/rework_2881_design_system_bereinigung.md (AC-1, AC-2)
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/molecules/__tests__/segment_feld_meldung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { SegmentFeldMeldung } from '../segmentFeldMeldung.ts';

const warte = (ms: number) => new Promise((r) => setTimeout(r, ms));

function aufbau() {
	const gemeldet: string[] = [];
	return { gemeldet, m: new SegmentFeldMeldung((w) => gemeldet.push(w)) };
}

describe('SegmentFeldMeldung', () => {
	test('fertiges Segment bzw. Kalender-Wahl wird sofort gemeldet', () => {
		const { gemeldet, m } = aufbau();
		m.aendern('2026-11-19', false);
		assert.deepEqual(gemeldet, ['2026-11-19']);
	});

	test('unfertiges Segment (Tag „2") bleibt zurück — auch nach einer Pause; das fertige ersetzt es', async () => {
		const { gemeldet, m } = aufbau();
		m.aendern('2026-08-02', true);
		await warte(400);
		assert.deepEqual(gemeldet, [], 'Zwischenstand nach Pause nicht gemeldet');
		m.aendern('2026-08-26', false);
		assert.deepEqual(gemeldet, ['2026-08-26']);
		m.abschliessen();
		assert.deepEqual(gemeldet, ['2026-08-26'], 'nichts Offenes mehr');
	});

	test('Feld verlassen meldet den offenen Wert (z. B. geleert = "")', () => {
		const { gemeldet, m } = aufbau();
		m.aendern('', true);
		assert.equal(m.offen, true);
		m.abschliessen();
		assert.deepEqual(gemeldet, ['']);
	});

	test('gleicher Wert wie gespeichert: verworfenes Offenes geht beim Verlassen nicht mehr hinaus', () => {
		const { gemeldet, m } = aufbau();
		m.aendern('2027-08-03', true);
		m.verwerfen();
		m.abschliessen();
		assert.deepEqual(gemeldet, []);
		m.aendern('2027-07-30', false);
		assert.deepEqual(gemeldet, ['2027-07-30']);
	});

	test('fremder Wertwechsel: gesperrt nimmt nichts an (auch nicht den Abbau-Stand), Freigabe meldet wieder', () => {
		const { gemeldet, m } = aufbau();
		m.aendern('2027-08-25', true);
		m.sperren();
		assert.equal(m.offen, false, 'Offenes verworfen');
		m.aendern('2027-01-25', false);
		m.aendern('2027-01-25', true);
		m.abschliessen();
		assert.deepEqual(gemeldet, [], 'nichts gemeldet, solange gesperrt');
		m.freigeben();
		m.abschliessen();
		assert.deepEqual(gemeldet, [], 'nichts aus der Sperrzeit nachgemeldet');
		m.aendern('2027-07-30', false);
		assert.deepEqual(gemeldet, ['2027-07-30']);
	});
});
