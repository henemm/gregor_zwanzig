// doc-compliance-test
//
// Issue #2276 Scheibe S6h (Epic #2345) — AC-2-Endbilanz.
// Spec: docs/specs/modules/rework_2276_s6h_ac2_endbilanz.md
//
// ZWECK
// -----
// Die Spec fuehrt im Anhang „AC-2-Endbilanz" alle 47 Eintraege der
// HERKUNFT-Ratsche (`context_herkunft_zweige_eingefroren.test.ts`) in drei
// Kategorien: FACHLICH (27), DARSTELLUNG (6), HERKUNFT (14). Dieser Test haelt
// die Doku-Tabelle mechanisch deckungsgleich mit der eingefrorenen Soll-Liste
// der Ratsche — in BEIDEN Richtungen. Wird die Ratsche nachgefuehrt, ohne die
// Endbilanz mitzuziehen (oder umgekehrt), wird er rot.
//
// SCHICHT-EINORDNUNG (Test-Politik, CLAUDE.md): Dies ist eine reine
// DOKU-KONSISTENZ-Pruefung via Source-Inspection — KEIN Verhaltensnachweis.
// Deshalb der Marker `doc-compliance-test` oben (Ausnahme zur Datei-Grep-Regel).
// Das Verhalten (Soll gegen echten Zaehlbefehl) bewacht die Ratsche selbst.
//
// WARUM ROHTEXT STATT IMPORT: `EINGEFROREN` ist in der Ratsche bewusst NICHT
// exportiert; die Ratsche bleibt unangetastet. Die 47 Eintraege werden deshalb
// aus dem Quelltext des Array-Literals extrahiert. Eine Positiv-Kontrolle
// (genau 47) verhindert, dass ein kaputter Extraktions-Regex vakuum-gruen
// durchlaeuft.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/ac2_endbilanz_deckt_alle_47_ab.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { vergleicheZweigListen } from './context_herkunft_zweige_eingefroren.test.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
// __tests__ -> shared -> components -> lib -> src -> frontend -> Repo-Wurzel
const REPO_WURZEL = join(HIER, '..', '..', '..', '..', '..', '..');
const SPEC = join(REPO_WURZEL, 'docs', 'specs', 'modules', 'rework_2276_s6h_ac2_endbilanz.md');
const RATSCHE = join(HIER, 'context_herkunft_zweige_eingefroren.test.ts');

const RATSCHE_ANFANG = 'const EINGEFROREN: readonly string[] = [';

/** Extrahiert die `'Datei:Zeile'`-Eintraege aus dem Array-Literal
 *  `EINGEFROREN` der Ratsche (Rohtext, kein Import). */
function extrahiereRatschenListe(): string[] {
	const quelle = readFileSync(RATSCHE, 'utf-8');
	const anfang = quelle.indexOf(RATSCHE_ANFANG);
	assert.ok(anfang >= 0, `Anfang von EINGEFROREN nicht gefunden in ${RATSCHE}`);
	const rest = quelle.slice(anfang + RATSCHE_ANFANG.length);
	const ende = rest.search(/^\];\s*$/m);
	assert.ok(ende >= 0, 'Schliessendes `];` von EINGEFROREN nicht gefunden');
	return rest
		.slice(0, ende)
		.split('\n')
		.map((z) => z.trim())
		.map((z) => /^'([^']+)',?$/.exec(z))
		.filter((m): m is RegExpExecArray => m !== null)
		.map((m) => m[1]);
}

/** Extrahiert die `Datei:Zeile`-Werte (erste Tabellenspalte, in Backticks)
 *  aus dem Spec-Abschnitt, dessen Ueberschrift mit `### <kategorie> (` beginnt.
 *  Der Abschnitt endet an der naechsten `##`/`###`-Ueberschrift. */
function extrahiereSpecKategorie(spec: string, kategorie: string): string[] {
	const zeilen = spec.split('\n');
	const start = zeilen.findIndex((z) => z.startsWith(`### ${kategorie} (`));
	assert.ok(start >= 0, `Spec-Abschnitt \`### ${kategorie} (\` nicht gefunden`);
	const eintraege: string[] = [];
	for (let i = start + 1; i < zeilen.length; i++) {
		const z = zeilen[i];
		if (/^#{2,3} /.test(z)) break;
		const m = /^\|\s*`([^`]+)`\s*\|/.exec(z);
		if (m) eintraege.push(m[1]);
	}
	return eintraege;
}

function leseSpec(): string {
	return readFileSync(SPEC, 'utf-8');
}

describe('S6h AC-2-Endbilanz: Spec-Tabelle deckt die Ratsche restlos ab', () => {
	test('Messflaeche ist ueberhaupt erreichbar (Schutz gegen falsches cwd)', () => {
		assert.ok(existsSync(SPEC), `Spec nicht gefunden (aufgeloest: ${SPEC})`);
		assert.ok(existsSync(RATSCHE), `Ratsche nicht gefunden (aufgeloest: ${RATSCHE})`);
	});

	test('aus der Ratsche extrahiert: genau 47 Eintraege (Positiv-Kontrolle des Regex)', () => {
		const ratsche = extrahiereRatschenListe();
		assert.strictEqual(
			ratsche.length,
			47,
			`Extraktion aus EINGEFROREN lieferte ${ratsche.length} statt 47 Eintraege`
		);
		assert.strictEqual(new Set(ratsche).size, ratsche.length, 'EINGEFROREN enthaelt Duplikate');
	});

	test('aus der Spec extrahiert: FACHLICH 27, DARSTELLUNG 6, HERKUNFT 14, Summe 47', () => {
		const spec = leseSpec();
		const fachlich = extrahiereSpecKategorie(spec, 'FACHLICH');
		const darstellung = extrahiereSpecKategorie(spec, 'DARSTELLUNG');
		const herkunft = extrahiereSpecKategorie(spec, 'HERKUNFT');
		assert.strictEqual(fachlich.length, 27, 'FACHLICH-Tabelle hat nicht 27 Eintraege');
		assert.strictEqual(darstellung.length, 6, 'DARSTELLUNG-Tabelle hat nicht 6 Eintraege');
		assert.strictEqual(herkunft.length, 14, 'HERKUNFT-Tabelle hat nicht 14 Eintraege');
		assert.strictEqual(fachlich.length + darstellung.length + herkunft.length, 47);
	});

	test('jeder Spec-Eintrag steht genau einmal (keine Duplikate, keine Kategorie-Ueberschneidung)', () => {
		const spec = leseSpec();
		const alle = ['FACHLICH', 'DARSTELLUNG', 'HERKUNFT'].flatMap((k) =>
			extrahiereSpecKategorie(spec, k).map((e) => ({ k, e }))
		);
		const gesehen = new Map<string, string>();
		const doppelt: string[] = [];
		for (const { k, e } of alle) {
			const vorher = gesehen.get(e);
			if (vorher !== undefined) doppelt.push(`${e} (${vorher} + ${k})`);
			else gesehen.set(e, k);
		}
		assert.deepStrictEqual(doppelt, [], `Mehrfach gefuehrte Spec-Eintraege: ${doppelt.join(', ')}`);
	});

	test('Ratsche und Spec-Endbilanz sind mengengleich — in beiden Richtungen', () => {
		const spec = leseSpec();
		const ratsche = extrahiereRatschenListe();
		const endbilanz = ['FACHLICH', 'DARSTELLUNG', 'HERKUNFT'].flatMap((k) =>
			extrahiereSpecKategorie(spec, k)
		);
		const { fehlt, zusaetzlich } = vergleicheZweigListen(ratsche, endbilanz);
		const alsListe = (e: string[]) => (e.length === 0 ? '—' : e.join(', '));
		assert.deepStrictEqual(
			{ fehlt, zusaetzlich },
			{ fehlt: [], zusaetzlich: [] },
			'AC-2-Endbilanz und HERKUNFT-Ratsche laufen auseinander.\n' +
				`  Ratsche (EINGEFROREN): ${ratsche.length}\n` +
				`  Spec-Endbilanz:        ${endbilanz.length}\n` +
				`  In der Ratsche, fehlt in der Spec: ${alsListe(fehlt)}\n` +
				`  In der Spec, fehlt in der Ratsche: ${alsListe(zusaetzlich)}\n` +
				'  Ratsche nachgefuehrt? Dann die Endbilanz in der Spec mitziehen (und umgekehrt).'
		);
	});
});
