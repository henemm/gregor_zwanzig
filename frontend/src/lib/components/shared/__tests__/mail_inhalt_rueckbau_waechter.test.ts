// TDD RED — Issue #2277 Scheibe S5: Waechter fuer den Rueckbau (AC-7) und
// "Ortsvergleich ohne Karte" (AC-8).
// Spec: docs/specs/modules/feat_2277_s5_reportconfig_rueckbau.md.
//
// doc-compliance-test: Struktur-Waechter (Existenz + Import-Scan). Er belegt
// KEIN Nutzerverhalten — das Verhalten des Bausteins steht in
// mail_inhalt_card*.test.ts und trip_new_mail_inhalt_karte_genau_eine_instanz.
// Dasselbe etablierte Muster wie legacy_wizard_removed.test.ts.
//
// Import-Scan: Kommentarzeilen werden ignoriert (erklaerende Verweise sind laut
// Spec erlaubt); gezaehlt wird jede Nicht-Kommentar-Zeile, die einen der drei
// Namen innerhalb eines Anfuehrungszeichen-Pfads nennt (import/export/dynamic
// import/readFileSync/pathToFileURL — alles, was die Datei ladet).
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/__tests__/mail_inhalt_rueckbau_waechter.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join, dirname, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const COMPONENTS = join(HERE, '..', '..');                // frontend/src/lib/components
const FRONTEND = join(COMPONENTS, '..', '..', '..');      // frontend
const REPO = join(FRONTEND, '..');
const SELF = fileURLToPath(import.meta.url);

function dateien(dir: string, out: string[] = []): string[] {
	if (!existsSync(dir)) return out;
	for (const name of readdirSync(dir)) {
		if (name === 'node_modules' || name === '.svelte-kit' || name === '__pycache__') continue;
		const p = join(dir, name);
		if (statSync(p).isDirectory()) dateien(p, out);
		else if (/\.(ts|js|mjs|svelte|py)$/.test(name)) out.push(p);
	}
	return out;
}

const NAMEN = /['"`][^'"`\n]*(EditReportConfigSection\.svelte|reportConfigWrite(\.ts)?|BriefingsTab\.svelte)[^'"`\n]*['"`]/;
const istKommentar = (z: string) => /^\s*(\/\/|\/\*|\*|#|<!--)/.test(z);

function ladeBezuege(wurzeln: string[], ausser: string[] = []): string[] {
	const treffer: string[] = [];
	for (const w of wurzeln) {
		for (const f of dateien(w)) {
			if (f === SELF || ausser.includes(f)) continue;
			readFileSync(f, 'utf-8').split('\n').forEach((z, i) => {
				if (!istKommentar(z) && NAMEN.test(z)) treffer.push(`${relative(REPO, f)}:${i + 1}: ${z.trim().slice(0, 120)}`);
			});
		}
	}
	return treffer;
}

describe('AC-7: Rueckbau von EditReportConfigSection, reportConfigWrite, BriefingsTab', () => {
	for (const rel of [
		'edit/EditReportConfigSection.svelte',
		'edit/reportConfigWrite.ts',
		'briefings-tab/BriefingsTab.svelte'
	]) {
		test(`datei_existiert_nicht_mehr__${rel.replace(/\W+/g, '_')}`, () => {
			assert.ok(!existsSync(join(COMPONENTS, rel)), `AC-7: ${rel} existiert noch (Ticket-AC-5 verlangt Rueckbau).`);
		});
	}

	test('kein_quell_test_oder_e2e_code_laedt_die_drei_dateien', () => {
		const treffer = ladeBezuege(
			[join(FRONTEND, 'src'), join(FRONTEND, 'e2e'), join(REPO, 'tests')],
			// Python-Konstante ohne Lesezugriff (Hygiene-Test #753, prueft nur "kein Test liest ..."):
			[join(REPO, 'tests', 'tdd', 'test_issue_753_746_hygiene.py')]
		);
		assert.deepEqual(treffer, [], `AC-7: ${treffer.length} Bezug/Bezuege auf geloeschte Dateien:\n${treffer.join('\n')}`);
	});

	test('TripTabs_importiert_BriefingsTab_nicht', () => {
		const q = readFileSync(join(COMPONENTS, 'trip-detail', 'TripTabs.svelte'), 'utf-8');
		const importZeilen = q.split('\n').filter((z) => /^\s*import\b/.test(z));
		assert.ok(!importZeilen.some((z) => /BriefingsTab/.test(z)), 'AC-7: TripTabs.svelte importiert BriefingsTab noch (toter Import).');
	});
});

// #3297/#3020: AC-8 (MailInhaltCard liegt in shared/) entfaellt — die Karte ist geloescht.
