// TDD RED — Issue #2276 Scheibe S6f (Epic #2345), AC-2 (= AC-4 aus #2276):
// nach dem Bridge-Umzug darf der Name der aufgeloesten Compare-Hub-
// Klebeschicht nirgendwo mehr woertlich unter frontend/src auftauchen — weder
// als Datei noch als Import-, Kommentar- oder Signatur-Erwaehnung.
//
// Spec: docs/specs/modules/rework_2276_s6f_bridge_umzug.md — AC-2
//
// Zwei Zusicherungen:
//   (a) die aufgeloeste Datei existiert nicht mehr,
//   (b) eine woertliche `grep -rn`-Suche ueber frontend/src liefert 0 Treffer.
//
// Der Suchbegriff wird aus ZWEI String-Teilen zusammengesetzt (niemals als
// zusammenhaengendes Literal in dieser Datei) — sonst faende die eigene Suche
// sich selbst und der Test waere strukturell nie gruen zu bekommen.
//
// Pfadregel #1409 / Praezedenz: Wurzel relativ zur EIGENEN Testdatei
// aufgeloest (Muster: shared/__tests__/context_herkunft_zweige_eingefroren.test.ts),
// niemals ueber einen festen Hauptrepo-Pfad (sonst falsches Gruen aus dem Worktree).
//
// grep-Exitcodes: 0 = Treffer, 1 = kein Treffer, 2 = grep selbst ist
// fehlgeschlagen (kaputtes Muster/Pfad). Nur 2 ist ein Messaufbau-Fehler —
// 1 ("keine Zeile") ist der erwuenschte GREEN-Fall und darf NICHT wie ein
// Fehler behandelt werden (Abweichung vom HERKUNFT-Ratschen-Muster, das
// pauschal `catch` als "leer" interpretiert).
//
// RED HEUTE: die Datei existiert noch (der Umzug dieser Scheibe steht noch
// aus) UND mehrere produktive Dateien (CompareTabs.svelte, routes/compare/
// +page.svelte, shared/alarmeVergleichSpeicherung.ts, shared/VersandTab.svelte,
// shared/versandVergleichSpeicherung.ts, shared/corridor-editor/
// wertebereicheVergleichSpeicherung.ts, shared/weather-metrics-tab/
// weatherMetricsCompareSave.ts) nennen den Namen noch woertlich (Kommentare) —
// deren Bereinigung ist NICHT Teil dieser TDD-RED-Phase (Produktivdateien).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_hub_bridge_restlos_entfernt.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

/** Wurzel der Messflaeche — relativ zur EIGENEN Testdatei aufgeloest.
 *  __tests__ -> compare -> components -> lib -> src. */
const SRC = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', '..');

/** Suchbegriff aus zwei Teilen zusammengesetzt — als zusammenhaengendes
 *  Literal wuerde diese Testdatei sich selbst als Treffer finden. */
const NAME_TEIL_1 = 'compareHub';
const NAME_TEIL_2 = 'WizardBridge';
const BEGRIFF = NAME_TEIL_1 + NAME_TEIL_2;

/** Pfad der aufgeloesten Datei — ebenfalls aus dem zusammengesetzten Begriff
 *  gebaut, keine woertliche Nennung im Quelltext. */
const AUFGELOESTE_DATEI = join(SRC, 'lib', 'components', 'compare', BEGRIFF + '.ts');

function grep(begriff: string): { status: number | null; treffer: string[]; stderr: string } {
	const lauf = spawnSync('grep', ['-rn', begriff, '.'], { cwd: SRC, encoding: 'utf-8' });
	const treffer = (lauf.stdout ?? '').split('\n').filter((z) => z.trim() !== '');
	return { status: lauf.status, treffer, stderr: lauf.stderr ?? '' };
}

describe('AC-2 (= AC-4 aus #2276): der Name der aufgeloesten Bridge steht nirgendwo mehr woertlich', () => {
	test('Messflaeche ist ueberhaupt erreichbar (Schutz gegen falsches cwd)', () => {
		assert.ok(
			existsSync(join(SRC, 'lib', 'components', 'compare', 'compareEditorSave.ts')),
			`SRC zeigt nicht auf frontend/src (aufgeloest: ${SRC})`
		);
	});

	test('Positiv-Kontrolle: der Messaufbau findet einen stabilen, unverdaechtigen Begriff', () => {
		const { status, treffer, stderr } = grep('CompareTabs');
		assert.notStrictEqual(status, 2, `grep selbst ist fehlgeschlagen (Status 2): ${stderr}`);
		assert.ok(
			treffer.length > 0,
			'Positiv-Kontrolle: der Messaufbau muss ueberhaupt Treffer finden koennen — ' +
				'sonst beweist "0 Treffer" beim eigentlichen Begriff unten gar nichts'
		);
	});

	test('die aufgeloeste Bridge-Datei (Name zusammengesetzt) existiert nicht mehr', () => {
		assert.strictEqual(
			existsSync(AUFGELOESTE_DATEI),
			false,
			`Datei existiert noch: ${AUFGELOESTE_DATEI} — der Umzug (AC-1) ist nicht abgeschlossen`
		);
	});

	test('grep -rn liefert 0 Treffer fuer den zusammengesetzten Begriff unter frontend/src', () => {
		const { status, treffer, stderr } = grep(BEGRIFF);
		assert.notStrictEqual(
			status,
			2,
			`grep selbst ist fehlgeschlagen (Status 2, kein "kein Treffer"-Fall): ${stderr}`
		);
		assert.deepStrictEqual(
			treffer,
			[],
			`AC-2 verletzt — ${treffer.length} woertliche Erwaehnung(en) von ${BEGRIFF} unter frontend/src:\n` +
				treffer.join('\n')
		);
	});
});
