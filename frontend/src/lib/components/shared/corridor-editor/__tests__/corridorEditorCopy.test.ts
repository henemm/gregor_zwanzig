// Issue #1425 Schritt 2, Teil 2, Scheibe C (Spec: docs/specs/fast/fix-1425-s2c-banner-text.md).
//
// Der Reiter "Wertebereiche" versprach eine Wirkung, die es dort nicht gibt:
// "außerhalb = Warnung … bekommst du zwischen den Briefings eine Sofort-Meldung."
// `corridor.notify` hat keinen Leser — die einzige Alarm-Quelle ist
// `display_config.metric_alert_levels` (src/services/trip_alert.py), bedient im
// Reiter *Alarme*. Der Text schickte Nutzer also an die falsche Stelle.
//
// Geprueft wird zweierlei:
//   1. AC-1/AC-2 — die ANGEZEIGTE Copy beider Editoren (Desktop + Mobil).
//      Reiner Textinhalt hat keine ausfuehrbare Logik, deshalb ein bewusst
//      markierter doc-compliance-Check (CLAUDE.md, Test-Politik). Er liest
//      ausschliesslich den Markup-Teil OHNE HTML-Kommentare — ein Kommentar,
//      der das alte Versprechen nur ERWAEHNT, darf nicht anschlagen.
//   2. AC-3 — der Markieren-Zaehler als echter Logik-Test gegen
//      countEffectiveMarks() (keine Datei-Inspektion).
//
// Ausfuehrung: cd frontend && npm test -- \
//   src/lib/components/shared/corridor-editor/__tests__/corridorEditorCopy.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

import { countEffectiveMarks, supportsMark } from '../corridorEditorState.ts';

// Pfadregel #1409: Prueflinge relativ zur EIGENEN Testdatei aufloesen (Worktree),
// nie ueber einen festen Hauptrepo-Pfad — sonst pruefte der Test aus dem Worktree
// die unveraenderte Hauptrepo-Kopie und meldete falsches Gruen.
const HERE = dirname(fileURLToPath(import.meta.url));
const EDITORS = {
	Desktop: resolve(HERE, '..', 'CorridorEditor.svelte'),
	Mobil: resolve(HERE, '..', 'CorridorEditorMobile.svelte')
} as const;

/**
 * Der Teil einer .svelte-Datei, den der Nutzer als Text zu sehen bekommt:
 * Markup ohne <script>, ohne <style> und ohne HTML-Kommentare.
 */
function visibleCopy(path: string): string {
	const src = readFileSync(path, 'utf-8');
	return src
		.replace(/<script[\s\S]*?<\/script>/g, '')
		.replace(/<style[\s\S]*?<\/style>/g, '')
		.replace(/<!--[\s\S]*?-->/g, '');
}

// Formulierungen, die eine Wirkung des Reiters behaupten, die er nicht hat.
const BROKEN_PROMISES = [
	'Sofort-Meldung',
	'außerhalb = ',
	'Warn-Schwellen',
	'Beide Wirkungen je Metrik frei kombinierbar'
];

const TRIP_LEAD =
	'Ein Wertebereich je Metrik legt fest, welche Werte du auf der Tour noch akzeptierst. Werte im ' +
	'Bereich werden im Briefing hervorgehoben. Warnungen zwischen den Briefings stellst du im ' +
	'Reiter Alarme ein.';

const COMPARE_LEAD =
	'Ein Wertebereich je Metrik legt deinen Idealbereich fest. Werte im Bereich werden im ' +
	'Briefing pro Ort grün markiert — kein Score, kein Ranking, nur eine Lese-Hilfe.';

/** Zeilenumbrueche/Einrueckung im Markup sind Layout, kein Text. */
function flat(s: string): string {
	return s.replace(/\s+/g, ' ').trim();
}

describe('AC-1/AC-2: der Wertebereiche-Reiter verspricht keine Wirkung, die er nicht hat', () => {
	for (const [variante, path] of Object.entries(EDITORS)) {
		test(`${variante}: keine Sofort-Meldung, keine "außerhalb ="-Wirkung, keine Warn-Schwellen`, () => {
			const copy = visibleCopy(path); // doc-compliance-test
			for (const phrase of BROKEN_PROMISES) {
				assert.equal(
					copy.includes(phrase),
					false,
					`AC-1/AC-2 FAIL (${variante}): der Reiter behauptet wieder "${phrase}". ` +
						'Der Wertebereiche-Reiter markiert nur — Warnungen zwischen den Briefings ' +
						'kommen ausschliesslich aus display_config.metric_alert_levels (Reiter Alarme). ' +
						'Solange corridor.notify keinen Leser hat, ist jedes Warn-Versprechen hier falsch.'
				);
			}
		});

		test(`${variante}: die Legende nennt nur noch "im Bereich = markiert"`, () => {
			const copy = flat(visibleCopy(path)); // doc-compliance-test
			assert.ok(
				copy.includes('im Bereich = <strong'),
				`AC-2 FAIL (${variante}): die Legenden-Zeile "im Bereich = markiert" fehlt.`
			);
			assert.equal(
				/swatch warn/.test(copy),
				false,
				`AC-2 FAIL (${variante}): das Warn-Swatch-Element der Legende ist wieder da.`
			);
		});

		test(`${variante}: der Trip-Text verweist auf den Reiter Alarme`, () => {
			const copy = flat(visibleCopy(path)); // doc-compliance-test
			assert.ok(
				copy.includes(flat(TRIP_LEAD)),
				`AC-1 FAIL (${variante}): der Trip-Einleitungstext lautet nicht wie freigegeben ` +
					'und/oder verweist nicht auf den Reiter Alarme.'
			);
			assert.ok(
				copy.includes('Sag mir, welche Werte für dich passen'),
				`AC-1 FAIL (${variante}): die Trip-Ueberschrift lautet nicht wie freigegeben.`
			);
		});

		test(`${variante}: der Ortsvergleich-Text bleibt woertlich unveraendert`, () => {
			const copy = flat(visibleCopy(path)); // doc-compliance-test
			assert.ok(
				copy.includes(flat(COMPARE_LEAD)),
				`AC-4 FAIL (${variante}): der Compare-Einleitungstext wurde mitveraendert — ` +
					'er war bereits ehrlich und bleibt unangetastet.'
			);
		});
	}
});

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
