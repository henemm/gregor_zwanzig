// doc-compliance-test (Ratschentest: liest Svelte-Quelltexte als DATEN)
//
// Issue #2649 (i18n S4, Epic #2644) — Ratsche Frontend: kein Textknoten und
// kein beschriftendes Attribut (title|aria-label|placeholder|alt|label) in
// einer Svelte-Datei unter frontend/src/ ausser ueber den Katalog. Altbestand
// steht in ../hardcode_allowlist.json und darf nur schrumpfen; beide
// Richtungen sind rot (Treffer ohne Eintrag UND Eintrag ohne Treffer).
// Spec: docs/specs/modules/i18n_s4_ratsche_frontend_2649.md
//
// Startstand (Messung 2026-10-31 auf origin/main 4f386528a + RED-Commit 5ef721c15):
// 253 gescannte Svelte-Dateien, 115 mit Treffern, 1115 Trefferzeilen,
// 33 Allowlist-Eintraege. Erzeugt mit
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     src/lib/i18n/__tests__/hardcode_scan.ts --messen
//
//   cd frontend && npm test -- src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
	scanneMarkup,
	wirdGescannt,
	pruefeGegenAllowlist,
	pruefeVerzeichnis,
	MINDEST_DATEIEN
} from './hardcode_scan.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const SRC = join(HIER, '..', '..', '..');
const FIXTURES = join(HIER, 'fixtures', 'hardcode');
const ALLOWLIST: string[] = JSON.parse(
	readFileSync(join(HIER, '..', 'hardcode_allowlist.json'), 'utf8')
);

function fixture(name: string) {
	return scanneMarkup(readFileSync(join(FIXTURES, name), 'utf8'));
}

describe('Scanner an Fixtures (AC-1, AC-2)', () => {
	test('AC-1: <button>Speichern</button> ist ein Textknoten-Treffer mit korrekter Zeile', () => {
		// Zeile 8 trotz 6 Zeilen <script> davor und <style> danach.
		assert.deepEqual(fixture('schlecht_button.svelte'), [
			{ zeile: 8, art: 'text', text: 'Speichern' }
		]);
	});

	test('AC-1: neue Komponente ausserhalb der Allowlist wird mit Datei:Zeile gemeldet', () => {
		const pfad = 'lib/components/neu_2649/NeueKomponente.svelte';
		const ergebnis = pruefeGegenAllowlist(
			[{ pfad, treffer: fixture('schlecht_button.svelte') }],
			ALLOWLIST
		);
		assert.deepEqual(ergebnis.ohneEintrag, [`${pfad}:8  "Speichern"`]);
	});

	test('AC-2: Katalog-Ausdruecke, Entities, Symbole und Kommentare sind keine Treffer', () => {
		assert.deepEqual(fixture('gut_button.svelte'), []);
		assert.deepEqual(fixture('gut_attribute.svelte'), []);
	});

	test('AC-2: statische placeholder/aria-label sind Attribut-Treffer, gemischte Werte nicht', () => {
		assert.deepEqual(fixture('schlecht_attribute.svelte'), [
			{ zeile: 7, art: 'attribut', text: 'Suche' },
			{ zeile: 8, art: 'attribut', text: 'Schließen' }
		]);
	});

	test('Zeilen bleiben bei mehrzeiligen Ausdruecken und Kommentaren erhalten', () => {
		const quelle = [
			'<!-- eins',
			'zwei -->',
			'{#each [1, 2] as n (n)}',
			'  <p>{n > 1 ? `{${n}}` : "}"}</p>',
			'{/each}',
			'<p>',
			'  Hallo   Welt',
			'</p>',
			'<Comp label="Ort" title=\'Karte\' aria-label="x" />'
		].join('\n');
		assert.deepEqual(scanneMarkup(quelle), [
			{ zeile: 7, art: 'text', text: 'Hallo Welt' },
			{ zeile: 9, art: 'attribut', text: 'Ort' },
			{ zeile: 9, art: 'attribut', text: 'Karte' }
		]);
	});
});

describe('Pfadauswahl (AC-6)', () => {
	test('__tests__/, routes/_design* und routes/email-preview-dev werden nicht gescannt', () => {
		for (const pfad of [
			'lib/i18n/__tests__/fixtures/hardcode/schlecht_button.svelte',
			'lib/components/shared/__tests__/Harness.svelte',
			'routes/_design/+page.svelte',
			'routes/_design-system/atoms/+page.svelte',
			'routes/email-preview-dev/+page.svelte'
		]) {
			assert.equal(wirdGescannt(pfad), false, pfad);
		}
	});

	test('alle uebrigen Svelte-Pfade (auch lib/components/ui/ und routes/) werden gescannt', () => {
		for (const pfad of [
			'lib/components/ui/button/button.svelte',
			'routes/+page.svelte',
			'routes/+layout.svelte',
			'routes/trips/[id]/+page.svelte',
			'lib/components/shared/VersandTab.svelte'
		]) {
			assert.equal(wirdGescannt(pfad), true, pfad);
		}
		assert.equal(wirdGescannt('lib/i18n/index.ts'), false);
	});
});

describe('Allowlist-Pruefung (AC-3)', () => {
	test('Verzeichnis-Eintrag mit / ist Praefix, Datei-Eintrag muss exakt passen', () => {
		const treffer = [{ zeile: 1, art: 'text' as const, text: 'Hallo' }];
		const ergebnisse = [
			{ pfad: 'routes/trips/+page.svelte', treffer },
			{ pfad: 'routes/tripsalt/+page.svelte', treffer },
			{ pfad: 'routes/+layout.svelte', treffer },
			{ pfad: 'routes/+page.svelte', treffer }
		];
		const ergebnis = pruefeGegenAllowlist(ergebnisse, ['routes/+layout.svelte', 'routes/trips/']);
		assert.deepEqual(ergebnis.ohneEintrag, [
			'routes/tripsalt/+page.svelte:1  "Hallo"',
			'routes/+page.svelte:1  "Hallo"'
		]);
		assert.deepEqual(ergebnis.eintraegeOhneTreffer, []);
	});

	test('Allowlist-Eintrag ohne Treffer ist rot und wird genannt', () => {
		const tot = 'lib/components/gibt_es_nicht_2649/';
		const ergebnis = pruefeVerzeichnis(SRC, [...ALLOWLIST, tot].sort());
		assert.deepEqual(ergebnis.ohneEintrag, []);
		assert.deepEqual(ergebnis.eintraegeOhneTreffer, [
			`Eintrag ohne Treffer: ${tot} – aus hardcode_allowlist.json streichen`
		]);
	});

	test('Allowlist ist sortiert, eindeutig und nicht leer', () => {
		assert.ok(ALLOWLIST.length > 0);
		assert.deepEqual([...new Set(ALLOWLIST)].sort(), ALLOWLIST);
	});

	test('echter Lauf ueber frontend/src: jeder Treffer liegt unter einem Eintrag, jeder Eintrag hat Treffer', () => {
		const ergebnis = pruefeVerzeichnis(SRC, ALLOWLIST);
		assert.deepEqual(
			ergebnis.ohneEintrag,
			[],
			'Hartkodierter Nutzertext ausserhalb der Allowlist — ueber den Katalog setzen ({$t(...)}):\n' +
				ergebnis.ohneEintrag.join('\n')
		);
		assert.deepEqual(ergebnis.eintraegeOhneTreffer, [], ergebnis.eintraegeOhneTreffer.join('\n'));
	});
});

describe('Messaufbau (AC-4)', () => {
	test(`weniger als ${MINDEST_DATEIEN} Dateien: leeres Verzeichnis bricht ab`, () => {
		const leer = mkdtempSync(join(tmpdir(), 'hardcode-scan-'));
		try {
			assert.throws(() => pruefeVerzeichnis(leer, ALLOWLIST), /Messaufbau leer/);
		} finally {
			rmSync(leer, { recursive: true, force: true });
		}
	});

	test('falsches Wurzelverzeichnis (nicht vorhanden bzw. zu klein) bricht ab', () => {
		assert.throws(() => pruefeVerzeichnis(join(SRC, 'gibt_es_nicht'), ALLOWLIST), /Messaufbau leer/);
		assert.throws(() => pruefeVerzeichnis(join(SRC, 'lib', 'i18n'), ALLOWLIST), /Messaufbau leer/);
	});

	test('Mindestzahl ist nicht abgesenkt', () => {
		assert.equal(MINDEST_DATEIEN, 150);
	});
});
