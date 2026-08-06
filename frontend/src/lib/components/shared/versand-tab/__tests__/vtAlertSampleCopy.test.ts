// Issue #1462 (Spec: docs/specs/fast/fix-1462-alarme-beispieltext.md).
//
// Der Reiter *Alarme* des Ortsvergleichs versprach ueber der Beispiel-Karte eine
// Wirkung, die es seit #1460 nicht mehr gibt: "wenn ein Wert den Wertebereich
// verlaesst". Der Wertebereich loest nichts mehr aus — Ausloeser sind
// Vorhersage-Aenderung, Nowcast und amtliche Warnung. Genau dasselbe falsche
// Versprechen hatte #1425 schon im Reiter *Wertebereiche* beseitigt; hier stand
// es nur an anderer Stelle weiter.
//
// Reiner Anzeigetext hat keine ausfuehrbare Logik — deshalb ein bewusst
// markierter doc-compliance-Check (CLAUDE.md, Test-Politik), Muster wie
// corridor-editor/__tests__/corridorEditorCopy.test.ts. Geprueft wird der
// Markup-Teil OHNE Kommentare: ein Kommentar, der den alten Wortlaut nur
// ERWAEHNT (wie dieser Header), darf nicht anschlagen.
//
// Ausfuehrung: cd frontend && npm test -- \
//   src/lib/components/shared/versand-tab/__tests__/vtAlertSampleCopy.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

// Pfadregel #1409: Pruefling relativ zur EIGENEN Testdatei aufloesen (Worktree),
// nie ueber einen festen Hauptrepo-Pfad.
const HERE = dirname(fileURLToPath(import.meta.url));
const SAMPLE = resolve(HERE, '..', 'VTAlertSample.svelte');
const ALARME_TAB = resolve(HERE, '..', '..', 'AlarmeTab.svelte');

/** Der Teil einer .svelte-Datei, den der Nutzer als Text zu sehen bekommt. */
function visibleCopy(path: string): string {
	return readFileSync(path, 'utf-8')
		.replace(/<script[\s\S]*?<\/script>/g, '')
		.replace(/<style[\s\S]*?<\/style>/g, '')
		.replace(/<!--[\s\S]*?-->/g, '');
}

/** Zeilenumbrueche/Einrueckung im Markup sind Layout, kein Text. */
function flat(s: string): string {
	return s.replace(/\s+/g, ' ').trim();
}

const NEUER_TEXT = 'So sieht eine ausgelöste Warn-Mail aus, wenn sich die Vorhersage deutlich ändert.';

// Formulierungen, die den Wertebereich als Ausloeser behaupten.
const FALSCHE_AUSLOESER = ['Wertebereich verlässt', 'Wertebereich verlaesst', 'Korridor verlässt'];

describe('AC-1/AC-2: die Beispiel-Warnung nennt den tatsaechlichen Ausloeser', () => {
	test('AC-1: der einleitende Satz nennt die Vorhersage-Aenderung', () => {
		const copy = flat(visibleCopy(SAMPLE)); // doc-compliance-test
		assert.ok(
			copy.includes(flat(NEUER_TEXT)),
			`AC-1 FAIL: der freigegebene Satz fehlt. Erwartet: "${NEUER_TEXT}"`
		);
	});

	test('AC-2: der Wertebereich wird nicht mehr als Ausloeser behauptet', () => {
		const copy = visibleCopy(SAMPLE); // doc-compliance-test
		for (const phrase of FALSCHE_AUSLOESER) {
			assert.equal(
				copy.includes(phrase),
				false,
				`AC-2 FAIL: die Beispiel-Warnung behauptet wieder "${phrase}". Seit #1460 loest der ` +
					'Wertebereich keinen Alarm mehr aus — Ausloeser sind Vorhersage-Aenderung, Nowcast ' +
					'und amtliche Warnung. Der Wertebereich markiert nur noch (#1371 S6, #1425).'
			);
		}
	});
});

describe('AC-3: der Trip-Zweig bleibt unberuehrt', () => {
	test('VTAlertSample wird im Alarme-Reiter nur im Vergleichs-Zweig gerendert', () => {
		const src = readFileSync(ALARME_TAB, 'utf-8');
		const mounts = src.match(/<VTAlertSample[^>]*>/g) ?? [];
		assert.equal(
			mounts.length,
			1,
			`AC-3 FAIL: erwartet genau eine <VTAlertSample>-Einbettung im Alarme-Reiter, gefunden ` +
				`${mounts.length}. Kaeme eine zweite ohne context="vergleich" dazu, traefe der Satz ` +
				'auch den Trip-Zweig, der stattdessen AlertPreviewCard zeigt.'
		);
		assert.match(
			mounts[0],
			/context="vergleich"/,
			'AC-3 FAIL: die Einbettung laeuft nicht mehr ausschliesslich im Vergleichs-Kontext.'
		);
	});
});
