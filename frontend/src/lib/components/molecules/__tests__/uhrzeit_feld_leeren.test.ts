// TDD RED — Issue #2502 (Umfangserweiterung #2947): Uhrzeitfeld leeren aus zweistelliger Stunde.
// Spec: docs/specs/fast/fix-2502-e2e-675-teardown.md — AC-3, AC-4.
//
// Fehler: Startzeit 15:00, im Stunden-Segment zweimal Rücktaste, Feld verlassen ⇒ gespeichert wird
// 01:00 statt „leer" (⇒ Standard 08:00). Ablauf im Feld: die erste Rücktaste lässt bits-ui die
// Stunde 1 melden, „01:00" bleibt als unfertiger Zwischenwert zurück; die zweite Rücktaste leert
// die Stunde, ohne dass bits-ui einen leeren Wert meldet; beim Verlassen ging bisher der
// zurückgehaltene Zwischenwert „01:00" hinaus.
//
// Vertrag (hier festgelegt, /50 baut danach) — neue Methode an SegmentFeldMeldung, die
// UhrzeitFeld.verlassen() beim Verlassen des Feldes aufruft:
//
//   verlassen(o: { beruehrt: boolean; unvollstaendig: boolean; leerMelden: boolean; gespeichert: string }): boolean
//     beruehrt       = der Nutzer hat das Feld seit dem letzten Aufbau angefasst
//     unvollstaendig = segmenteUnvollstaendig(feld): ein Ziffern-Segment ist leer/angefangen („––")
//     leerMelden     = Prop des Feldes (Etappen-Startzeit: '' heißt „zurück auf 08:00")
//     gespeichert    = aktueller Modellwert (`value`)
//   Rückgabe: true = das Feld wurde geleert verlassen (UhrzeitFeld baut dann die Segmente neu auf).
//   Regeln:
//     * berührt und unvollständig ⇒ geleert: ein zurückgehaltener Zwischenwert wird VERWORFEN
//       (nie gemeldet); mit leerMelden und gespeichert ≠ '' wird genau einmal '' gemeldet.
//     * sonst ⇒ wie abschliessen(): offener Wert wird gemeldet, Rückgabe false.
//
// Die Wirkstelle im Browser prüfen frontend/e2e/issue-675-stage-start-time.spec.ts (AC-5, gegen
// Staging) und design-system-trip-vergleich.spec.ts (DS-2, Leeren aus 07:30).
//
//   cd frontend && npm test -- src/lib/components/molecules/__tests__/uhrzeit_feld_leeren.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { SegmentFeldMeldung } from '../segmentFeldMeldung.ts';

function aufbau() {
	const gemeldet: string[] = [];
	const m = new SegmentFeldMeldung((w) => gemeldet.push(w)) as SegmentFeldMeldung & {
		verlassen?: (o: { beruehrt: boolean; unvollstaendig: boolean; leerMelden: boolean; gespeichert: string }) => boolean;
	};
	assert.equal(typeof m.verlassen, 'function', 'TDD RED: SegmentFeldMeldung.verlassen() fehlt');
	return { gemeldet, m: m as SegmentFeldMeldung & { verlassen: NonNullable<typeof m.verlassen> } };
}

describe('SegmentFeldMeldung.verlassen — Leeren aus zweistelliger Stunde (#2947)', () => {
	test('AC-3: 15:00 → Rücktaste (01:00 offen) → Rücktaste (Stunde leer) → verlassen ⇒ gemeldet nur "", nie "01:00"', () => {
		const { gemeldet, m } = aufbau();
		m.aendern('01:00', true); // erste Rücktaste: bits-ui meldet Stunde 1, Segment unfertig
		assert.deepEqual(gemeldet, [], 'Zwischenwert geht nicht vorzeitig hinaus');
		const geleert = m.verlassen({ beruehrt: true, unvollstaendig: true, leerMelden: true, gespeichert: '15:00' });
		assert.deepEqual(gemeldet, [''], 'geleert verlassen meldet "" (⇒ 08:00), nicht den Zwischenwert 01:00');
		assert.equal(geleert, true);
		assert.equal(m.offen, false, 'nichts Offenes mehr');
	});

	test('geleert ohne leerMelden: Zwischenwert wird verworfen, nichts gemeldet', () => {
		const { gemeldet, m } = aufbau();
		m.aendern('01:00', true);
		const geleert = m.verlassen({ beruehrt: true, unvollstaendig: true, leerMelden: false, gespeichert: '15:00' });
		assert.deepEqual(gemeldet, []);
		assert.equal(geleert, true);
		assert.equal(m.offen, false);
	});

	test('AC-4: Leeren aus 07:30 ohne Zwischenwert (DS-2) meldet weiterhin genau einmal ""', () => {
		const { gemeldet, m } = aufbau();
		const geleert = m.verlassen({ beruehrt: true, unvollstaendig: true, leerMelden: true, gespeichert: '07:30' });
		assert.deepEqual(gemeldet, ['']);
		assert.equal(geleert, true);
	});

	test('schon leer gespeichert: geleert verlassen meldet nichts', () => {
		const { gemeldet, m } = aufbau();
		m.verlassen({ beruehrt: true, unvollstaendig: true, leerMelden: true, gespeichert: '' });
		assert.deepEqual(gemeldet, []);
	});

	test('AC-4: vollständig verlassen meldet den offenen Wert wie bisher (Teil-Eingabe „1" ⇒ 01:00 beim Verlassen)', () => {
		const { gemeldet, m } = aufbau();
		m.aendern('01:30', true);
		const geleert = m.verlassen({ beruehrt: true, unvollstaendig: false, leerMelden: true, gespeichert: '07:30' });
		assert.deepEqual(gemeldet, ['01:30']);
		assert.equal(geleert, false);
	});

	test('AC-4: fertig getippte Uhrzeit wurde sofort gemeldet, Verlassen meldet nichts doppelt', () => {
		const { gemeldet, m } = aufbau();
		m.aendern('15:00', false);
		m.verlassen({ beruehrt: true, unvollstaendig: false, leerMelden: true, gespeichert: '15:00' });
		assert.deepEqual(gemeldet, ['15:00']);
	});

	test('unberührtes, leeres Feld verlassen (z. B. Kalender öffnen) meldet nichts und gilt nicht als geleert', () => {
		const { gemeldet, m } = aufbau();
		const geleert = m.verlassen({ beruehrt: false, unvollstaendig: true, leerMelden: true, gespeichert: '' });
		assert.deepEqual(gemeldet, []);
		assert.equal(geleert, false);
	});
});
