// doc-compliance-test
//
// Issue #1379 (Nachfolger von #1280): Die Versandzeit wird ueber eine
// Auswahlliste mit den 24 vollen Stunden gewaehlt — ein frei beschreibbares
// Uhrzeit-Feld (mit Minuten) gibt es nicht mehr. Der Schutzzweck des alten
// step={3600}-Tests bleibt: an dieser Stelle darf keine Minuten-Eingabe
// entstehen. Nur der Mechanismus aendert sich (Eingabefeld -> Auswahlliste).
//
// Spec: docs/specs/modules/versandzeit_stundenwahl.md (AC-1, AC-3)
//
// Source-Inspection-Test (kein DOM-Rendering, keine Mocks — Svelte-5-Komponenten
// sind ohne @testing-library/svelte in diesem Setup nicht mountbar). Die
// Auswahl-LOGIK (Stunden-Liste, Bestandswert-Kappung, AC-5) ist als echter
// Verhaltenstest in src/lib/utils/time.test.ts abgedeckt, das gerenderte
// Verhalten in e2e/versandzeit-stundenwahl.spec.ts; hier wird geprueft, dass die
// Komponente genau diese Logik verwendet und kein Eingabefeld mehr rendert.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { HOUR_OPTIONS, toHourOption } from '../../../../utils/time.ts';

const here = dirname(fileURLToPath(import.meta.url));
const VT_SCHEDULE_PLAN = join(here, '..', 'VTSchedulePlan.svelte');
const VERSAND_TAB = join(here, '..', '..', 'VersandTab.svelte');

/**
 * Extrahiert den kompletten Element-Block (oeffnender Tag), der einen
 * gegebenen data-testid traegt — inklusive Tag-Namen davor, damit geprueft
 * werden kann, WELCHES Element den testid traegt.
 */
function extractTagBlock(src: string, testid: string): string {
	const marker = `data-testid="${testid}"`;
	const markerIdx = src.indexOf(marker);
	assert.ok(markerIdx >= 0, `data-testid="${testid}" nicht gefunden`);
	const tagStart = src.lastIndexOf('<', markerIdx);
	assert.ok(tagStart >= 0, `kein oeffnender Tag vor data-testid="${testid}" gefunden`);
	const tagEnd = src.indexOf('>', markerIdx);
	assert.ok(tagEnd >= 0, `kein schliessendes > nach data-testid="${testid}" gefunden`);
	return src.slice(tagStart, tagEnd + 1);
}

describe('AC-1: VTSchedulePlan.svelte bietet die Versandzeit als Stunden-Auswahlliste an', () => {
	test('VTSchedulePlan.svelte existiert (geteilte Komponente)', () => {
		assert.ok(existsSync(VT_SCHEDULE_PLAN), 'VTSchedulePlan.svelte fehlt');
	});

	for (const testid of ['report-morning-time', 'report-evening-time']) {
		test(`${testid} ist eine Auswahlliste, kein frei beschreibbares Uhrzeit-Feld`, () => {
			const src = readFileSync(VT_SCHEDULE_PLAN, 'utf-8');
			const block = extractTagBlock(src, testid);
			assert.ok(
				/^<Select[\s>]/.test(block) || /^<select[\s>]/.test(block),
				`${testid} muss eine Auswahlliste (<Select>/<select>) sein, aktueller Block:\n${block}`
			);
			assert.ok(
				!/<input/i.test(block) && !/type="time"/.test(block),
				`${testid} darf kein <input type="time"> mehr sein, aktueller Block:\n${block}`
			);
		});

		test(`${testid} bezieht seinen Wert ueber toHourOption (Bestandswert-Kappung, AC-5)`, () => {
			const src = readFileSync(VT_SCHEDULE_PLAN, 'utf-8');
			const block = extractTagBlock(src, testid);
			assert.ok(
				/value=\{[^}]*HourOption[^}]*\}/.test(block),
				`${testid} muss seinen angezeigten Wert aus toHourOption(...) ableiten, aktueller Block:\n${block}`
			);
		});
	}

	test('die Optionen kommen aus der geteilten HOUR_OPTIONS-Liste (24 volle Stunden)', () => {
		const src = readFileSync(VT_SCHEDULE_PLAN, 'utf-8');
		assert.ok(
			/import \{[^}]*HOUR_OPTIONS[^}]*\} from '\$lib\/utils\/time'/.test(src),
			'VTSchedulePlan.svelte muss HOUR_OPTIONS aus $lib/utils/time importieren (keine eigene Liste)'
		);
		assert.ok(
			/\{#each HOUR_OPTIONS as /.test(src),
			'die Optionen muessen ueber {#each HOUR_OPTIONS ...} gerendert werden'
		);
		// Gegenprobe auf die Liste selbst (echter Wert, kein Datei-Text):
		assert.equal(HOUR_OPTIONS.length, 24);
		assert.equal(toHourOption('07:30'), '07:00');
	});

	test('kein type="time"-Eingabefeld mehr in der gesamten Komponente', () => {
		const src = readFileSync(VT_SCHEDULE_PLAN, 'utf-8');
		assert.ok(
			!src.includes('type="time"'),
			'VTSchedulePlan.svelte darf kein <input type="time"> mehr enthalten (Minuten waeren eintippbar)'
		);
	});

	// AC-3 / Trip-Compare-Teilungs-Invariante (CLAUDE.md): der Fix darf NICHT
	// dupliziert werden — es gibt genau EINEN Import-/Nutzungsort, der beide
	// Kontexte (context="route" implizit als Default, context="vergleich"
	// explizit) mit derselben Komponente bedient.
	test('VersandTab.svelte nutzt dieselbe VTSchedulePlan-Instanz fuer route UND vergleich (kein Duplikat)', () => {
		assert.ok(existsSync(VERSAND_TAB), 'VersandTab.svelte fehlt');
		const src = readFileSync(VERSAND_TAB, 'utf-8');
		const importCount = (src.match(/import VTSchedulePlan from '\.\/versand-tab\/VTSchedulePlan\.svelte'/g) || [])
			.length;
		assert.equal(importCount, 1, 'VTSchedulePlan darf nur EINMAL importiert werden (geteilte Komponente)');

		const usageCount = (src.match(/<VTSchedulePlan/g) || []).length;
		assert.equal(
			usageCount,
			2,
			'VTSchedulePlan muss fuer BEIDE Kontexte (route + vergleich) verwendet werden, keine eigene Kopie je Kontext'
		);
		assert.ok(
			src.includes('context="vergleich"'),
			'die vergleich-Verwendung muss context="vergleich" explizit setzen'
		);
	});
});
