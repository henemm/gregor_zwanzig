// Ratsche fuer Issue #2276 Scheibe S6b (Epic #2345) — AC-6.
// Spec: docs/specs/modules/rework_2276_s6b_wetter_metriken.md
//
// ZWECK
// -----
// Die 68er/67er-Ratsche (`context_herkunft_zweige_eingefroren.test.ts`) misst
// NUR `frontend/src/lib/components/shared/`. Der lebende Praezedenzfall der
// Umstellung (#1720 S1, CompareOutlookLayoutControls) hat dabei nachweislich
// `wiz`-Zugriffe ins ELTERNTEIL verschoben — dorthin, wo jene Ratsche nicht
// hinsieht. Eine Umstellung koennte also eine HERKUNFT-Verzweigung aus
// `shared/` heraus- und in `compare/`/`compare-new/` hineinschieben, und die
// Zahl faellt trotzdem. Genau dagegen steht diese zweite Messflaeche.
//
// 🔴 Das ist eine STRUKTURELLE RATSCHE, KEIN Verhaltensnachweis — und sie ist
// bereits in der RED-Phase gruen. Der Verhaltensbeleg der Umstellung ist AC-2
// (`frontend/e2e/compare-stundenverlauf-wertprops.spec.ts`), die Wirkort-
// Messung der Verdrahtung ist `compare_stundenverlauf_wertprops.test.ts`.
// Diese Datei sichert nur zu, dass die Umstellung nichts VERSCHIEBT. Sie wird
// rot, sobald eine `context`-Verzweigung ausserhalb von `shared/` hinzukommt.
//
// Pfadregel #1409: die Messflaeche wird relativ zur EIGENEN Testdatei
// aufgeloest, nie ueber einen festen Hauptrepo-Pfad (sonst misst der Test aus
// dem Worktree die unveraenderte Hauptrepo-Kopie).
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/context_herkunft_baseline_ausserhalb_shared.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { execSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

/** __tests__ -> shared -> components -> lib -> src */
const SRC = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', '..');

/** Derselbe Zaehlbefehl wie in der Schwester-Ratsche, nur mit umgekehrtem
 *  Blickfeld: ALLES unter `src/` AUSSER `shared/`. */
const ZAEHLBEFEHL =
	`grep -rn 'context ===\\|context !==' . --include='*.svelte' --include='*.ts'` +
	` | grep -v '/shared/' | grep -v __tests__ | grep -vE ':\\s*(\\*|//|/\\*)'`;

/** Eingefrorener Ist-Stand vom 2026-09-21 (vor der S6b-Umstellung), als
 *  Literal — kein Verzeichnis-Scan auf der Soll-Seite (sonst vakuum-gruen,
 *  Memory `ratsche_leeren_macht_den_abhaengigen_test_vakuum_gruen`). */
const BASELINE: readonly string[] = [
	'lib/components/organisms/MetricsEditorContextBar.svelte:53',
	'lib/components/organisms/MetricsEditorContextBar.svelte:60',
	'lib/components/organisms/MetricsEditorContextBar.svelte:94'
];

function messeIstListe(): string[] {
	let ausgabe = '';
	try {
		ausgabe = execSync(ZAEHLBEFEHL, { cwd: SRC, encoding: 'utf-8', shell: '/bin/bash' });
	} catch (e) {
		// grep endet mit 1, wenn die Pipeline leer bleibt.
		ausgabe = (e as { stdout?: string }).stdout ?? '';
	}
	return ausgabe
		.split('\n')
		.filter((z) => z.trim() !== '')
		.map((z) => {
			const m = /^(?:\.\/)?(.+?):(\d+):/.exec(z);
			assert.ok(m, `Zeile passt nicht zum grep -rn-Format: ${JSON.stringify(z)}`);
			return `${m[1]}:${m[2]}`;
		});
}

describe('AC-6: ausserhalb von shared/ entsteht keine neue HERKUNFT-Verzweigung', () => {
	test('Messflaeche ist ueberhaupt erreichbar (Schutz gegen falsches cwd)', () => {
		assert.ok(
			existsSync(join(SRC, 'lib', 'components', 'organisms', 'MetricsEditorContextBar.svelte')),
			`SRC zeigt nicht auf frontend/src (aufgeloest: ${SRC})`
		);
	});

	test('die Aussen-Baseline ist unveraendert — 3 Fundstellen, alle in der Kontext-Leiste', () => {
		const ist = messeIstListe();
		assert.deepStrictEqual(
			[...ist].sort(),
			[...BASELINE].sort(),
			'AC-6 FAIL: die Aussen-Baseline hat sich veraendert.\n' +
				`  Soll (eingefroren, 3): ${BASELINE.join(', ')}\n` +
				`  Ist (Zaehlbefehl, ${ist.length}): ${ist.join(', ') || '—'}\n` +
				'  Eine Umstellung darf eine HERKUNFT-Verzweigung ENTFERNEN, nicht aus\n' +
				'  shared/ heraus in eine Aufrufstelle VERSCHIEBEN.'
		);
	});

	test('in compare/ und compare-new/ steht weiterhin KEINE einzige', () => {
		const ist = messeIstListe();
		const verschoben = ist.filter((e) => e.includes('/compare/') || e.includes('/compare-new/'));
		assert.deepStrictEqual(
			verschoben,
			[],
			'AC-6 FAIL: eine `context`-Verzweigung ist in der Ortsvergleich-Flaeche gelandet: ' +
				`${verschoben.join(', ')}. Genau dorthin verschiebt der Praezedenzfall ` +
				'seine Zugriffe, wenn der Umbau nicht vollstaendig ist.'
		);
	});
});
