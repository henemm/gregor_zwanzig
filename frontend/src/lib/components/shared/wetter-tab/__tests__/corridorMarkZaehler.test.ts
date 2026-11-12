// Issue #1425 Schritt 2, Teil 2, Scheibe C (Spec: docs/specs/fast/fix-1425-s2c-banner-text.md),
// AC-3: der Markieren-Zaehler als echter Logik-Test gegen countEffectiveMarks().
//
// #2794 S3a Teil-PR 4a (AC-31): die Faelle AC-1/AC-2 (angezeigte Copy des alten
// Reiters Wertebereiche, CorridorEditor/CorridorEditorMobile) sind mit der
// Oberflaeche entfernt; die Logik (corridorEditorState.ts) zog nach shared/wetter-tab/
// um, dieser Test mit ihr (vorher corridor-editor/__tests__/corridorEditorCopy.test.ts).
//
// Ausfuehrung: cd frontend && npm test -- \
//   src/lib/components/shared/wetter-tab/__tests__/corridorMarkZaehler.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { countEffectiveMarks, supportsMark } from '../corridorEditorState.ts';

// --- AC-3: Zaehler (echter Logik-Test, keine Datei-Inspektion) -------------

/** Zeilen wie sie der Trip-Reiter aufbaut: drei Tages-Summen + zwei Extrema. */
const ROWS = [
	{ metric: 'sunny_hours_h', mark: true }, // Tages-Summe: Schalter unsichtbar
	{ metric: 'precipitation_sum', mark: true }, // Tages-Summe: Schalter unsichtbar
	{ metric: 'snow_new_sum_cm', mark: true }, // Tages-Summe: Schalter unsichtbar
	{ metric: 'wind_gust', mark: true }, // wirksam
	{ metric: 'temperature_max', mark: false } // wirksam, aber nicht markiert
];

describe('AC-3: der Markieren-Zaehler zaehlt nur, was supportsMark zulaesst', () => {
	test('Trip: gesetzte Marken auf Tages-Summen zaehlen nicht mit', () => {
		assert.equal(
			countEffectiveMarks(ROWS, 'route'),
			1,
			'AC-3 FAIL: der Zaehler nennt Marken auf Tages-Summen mit, deren Schalter seit ' +
				'Scheibe A unsichtbar ist — die Zahl waere hoeher als das, was der Nutzer sieht.'
		);
	});

	test('Ortsvergleich: dieselben Zeilen zaehlen alle vier Marken', () => {
		assert.equal(
			countEffectiveMarks(ROWS, 'vergleich'),
			4,
			'AC-4 FAIL: im Ortsvergleich markieren auch Tages-Aggregate korrekt — ' +
				'dort darf der Zaehler nichts unterschlagen.'
		);
	});

	test('die Zahl entspricht in beiden Kontexten genau den sichtbaren, gesetzten Schaltern', () => {
		for (const context of ['route', 'vergleich'] as const) {
			const visiblyMarked = ROWS.filter((r) => r.mark && supportsMark(r.metric, context)).length;
			assert.equal(
				countEffectiveMarks(ROWS, context),
				visiblyMarked,
				`AC-3 FAIL (${context}): Zaehler und Schalter-Sichtbarkeit stammen nicht aus ` +
					'derselben Entscheidung (supportsMark).'
			);
		}
	});

	test('keine Zeile / keine Marke ergibt 0', () => {
		assert.equal(countEffectiveMarks([], 'route'), 0);
		assert.equal(countEffectiveMarks(ROWS.map((r) => ({ ...r, mark: false })), 'route'), 0);
	});

	test('eine unbekannte Metrik-ID zaehlt mit (ihr Schalter ist sichtbar)', () => {
		assert.equal(
			countEffectiveMarks([{ metric: 'voellig_unbekannte_groesse_xyz', mark: true }], 'route'),
			1,
			'AC-3 FAIL: ausgeblendet — und damit nicht gezaehlt — werden ausschliesslich die drei ' +
				'bekannten Tages-Summen.'
		);
	});
});
