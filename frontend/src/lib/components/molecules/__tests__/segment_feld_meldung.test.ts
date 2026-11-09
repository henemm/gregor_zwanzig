// Issue #2881 Lieferung B — Melde-Regel der Segment-Felder (DatumFeld/UhrzeitFeld):
// Zwischenstände beim Tippen gehen nie nach außen, Kalender-/Programm-Wahl sofort, ein fremder
// Wertwechsel verwirft Offenes und sperrt bis zur Freigabe. Echte Klasse, echte Zeitgeber.
// Spec: docs/specs/modules/rework_2881_design_system_bereinigung.md (AC-1, AC-2)
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/molecules/__tests__/segment_feld_meldung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { SegmentFeldMeldung } from '../segmentFeldMeldung.ts';

const warte = (ms: number) => new Promise((r) => setTimeout(r, ms));

function aufbau(ruheMs = 20) {
	const gemeldet: string[] = [];
	return { gemeldet, m: new SegmentFeldMeldung((w) => gemeldet.push(w), ruheMs) };
}

describe('SegmentFeldMeldung', () => {
	test('Wahl ohne Tippen (Kalender) wird sofort gemeldet', () => {
		const { gemeldet, m } = aufbau();
		m.aendern('2026-11-19', false);
		assert.deepEqual(gemeldet, ['2026-11-19']);
	});

	test('Tippen: Zwischenstände (Monat „0" ⇒ Januar) gehen nicht hinaus, nur der Endstand nach der Ruhezeit', async () => {
		const { gemeldet, m } = aufbau();
		for (const zwischen of ['2027-08-02', '2027-08-20', '2027-01-20', '2027-08-20']) m.aendern(zwischen, true);
		assert.deepEqual(gemeldet, [], 'während des Tippens nichts gemeldet');
		await warte(60);
		assert.deepEqual(gemeldet, ['2027-08-20']);
	});

	test('Feld verlassen meldet den offenen Wert sofort, danach nicht noch einmal', async () => {
		const { gemeldet, m } = aufbau();
		m.aendern('07:30', true);
		m.abschliessen();
		assert.deepEqual(gemeldet, ['07:30']);
		await warte(60);
		assert.deepEqual(gemeldet, ['07:30']);
	});

	test('fremder Wertwechsel: Offenes verworfen, Rückschreiben gesperrt bis zur Freigabe', async () => {
		const { gemeldet, m } = aufbau();
		m.aendern('2027-08-20', true);
		m.sperren();
		m.aendern('2027-08-20', false); // bits-ui schreibt die alten Segmente zurück
		await warte(60);
		assert.deepEqual(gemeldet, [], 'weder der offene noch der zurückgeschriebene Wert');
		m.freigeben();
		m.aendern('2027-07-30', false);
		assert.deepEqual(gemeldet, ['2027-07-30']);
	});
});
