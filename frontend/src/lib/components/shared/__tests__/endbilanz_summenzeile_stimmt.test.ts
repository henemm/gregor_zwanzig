// # doc-compliance-test
// TDD RED — Issue #2727 (Epic #2345, DoD-1): compareWizardState ablösen.
// Spec: docs/specs/modules/feat_2727_compare_wizardstate_abloesen.md — AC-23
//
// Die AC-2-Endbilanz der HERKUNFT-Ratsche (docs/specs/modules/rework_2276_s6h_ac2_endbilanz.md)
// listet die eingefrorenen `context ===`-Zweige in drei Tabellen (FACHLICH / DARSTELLUNG / HERKUNFT).
// Die Summenzeile darunter muss zu den Tabellen passen: 27 + 5 + 15 = 47 (= `EINGEFROREN_SOLL_ANZAHL`
// in context_herkunft_zweige_eingefroren.test.ts). Gezählt werden die echten Tabellenzeilen, nicht
// die Überschrift — die Summenzeile wird gegen die Zählung abgeglichen.
//
// Doku-Compliance-Test (Ausnahme der Test-Politik): der Prüfling IST eine Doku-Datei; es gibt
// keinen Verhaltensnachweis für eine Summenzeile.
//
// Warum heute rot: die Summenzeile sagt „14 HERKUNFT = 46", die Tabelle hat 15 Zeilen (gesamt 47).
// Die Korrektur der Doku ist Teil der Implementierung (#2727), nicht dieser RED-Phase.
//
// Ausführen (aus frontend/):
//   node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks \
//     --test src/lib/components/shared/__tests__/endbilanz_summenzeile_stimmt.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// __tests__ -> shared -> components -> lib -> src -> frontend -> Repo-Wurzel
const REPO = resolve(dirname(fileURLToPath(import.meta.url)), ...Array(6).fill('..'));
const DOKU = join(REPO, 'docs', 'specs', 'modules', 'rework_2276_s6h_ac2_endbilanz.md');
const quelle = readFileSync(DOKU, 'utf-8');

/** Tabellenzeilen (Datei:Zeile-Einträge) des Abschnitts `### <titel> (…)` bis zur nächsten Überschrift. */
function abschnitt(titel: string): { ueberschriftZahl: number; zeilen: string[] } {
	const zeilen = quelle.split('\n');
	const start = zeilen.findIndex((z) => z.startsWith(`### ${titel} (`));
	assert.ok(start >= 0, `Messaufbau: Abschnitt „### ${titel}" fehlt in der Endbilanz`);
	const ueberschriftZahl = Number(/\((\d+)\s/.exec(zeilen[start])?.[1]);
	const eintraege: string[] = [];
	for (let i = start + 1; i < zeilen.length && !zeilen[i].startsWith('#'); i++) {
		if (/^\|\s*`[^`]+:\d+`\s*\|/.test(zeilen[i])) eintraege.push(zeilen[i]);
	}
	return { ueberschriftZahl, zeilen: eintraege };
}

const fachlich = abschnitt('FACHLICH');
const darstellung = abschnitt('DARSTELLUNG');
const herkunft = abschnitt('HERKUNFT');

describe('AC-23: Summenzeile der AC-2-Endbilanz stimmt mit den Tabellen überein', () => {
	test('Messaufbau: die drei Tabellen haben 27 / 5 / 15 Einträge, passend zu ihren Überschriften', () => {
		assert.equal(fachlich.zeilen.length, 27);
		assert.equal(darstellung.zeilen.length, 5);
		assert.equal(herkunft.zeilen.length, 15);
		assert.equal(fachlich.ueberschriftZahl, fachlich.zeilen.length);
		assert.equal(darstellung.ueberschriftZahl, darstellung.zeilen.length);
		assert.equal(herkunft.ueberschriftZahl, herkunft.zeilen.length);
	});

	test('die Summenzeile nennt 15 HERKUNFT und 47 insgesamt (= Summe der Tabellenzeilen)', () => {
		const summe = /\*\*Summe:\*\*\s*(\d+)\s*FACHLICH\s*\+\s*(\d+)\s*DARSTELLUNG\s*\+\s*(\d+)\s*HERKUNFT\s*=\s*\*\*(\d+)\*\*/.exec(quelle);
		assert.ok(summe, 'Summenzeile „**Summe:** N FACHLICH + N DARSTELLUNG + N HERKUNFT = **N**" nicht gefunden');
		const [, f, d, h, gesamt] = summe!.map(Number);
		assert.equal(f, fachlich.zeilen.length, 'FACHLICH in der Summenzeile');
		assert.equal(d, darstellung.zeilen.length, 'DARSTELLUNG in der Summenzeile');
		assert.equal(h, herkunft.zeilen.length, `HERKUNFT in der Summenzeile: ${h}, Tabelle: ${herkunft.zeilen.length}`);
		const gezaehlt = fachlich.zeilen.length + darstellung.zeilen.length + herkunft.zeilen.length;
		assert.equal(gesamt, gezaehlt, `Gesamtzahl in der Summenzeile: ${gesamt}, gezählt: ${gezaehlt}`);
		assert.equal(gesamt, 47);
	});
});
