// Issue #1256 Scheibe 7 — AC-20: CompareMatrix.svelte und HourlyMatrix.svelte
// (Best-Value-Hervorhebung, "Top-3 Locations") sind bestaetigter Totcode:
// ausserhalb ihrer eigenen Testdateien existiert KEIN produktiver Import.
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md § AC-20
// ("Statischer Grep-Test auf beide Dateipfade, 0 Treffer ausserhalb
// __tests__/"). Dieser Test ist ein Bestandsnachweis (analog AC-19) und
// darf bereits in der RED-Phase gruen sein — er waecht dagegen, dass die
// Neutralitaets-Grauzone je wieder produktiv verdrahtet wird (Constraint 1:
// kein Score, kein Rang, keine Empfehlung).
//
// Bewusst ein Import-Statement-Match (from '...X.svelte'), keine blosse
// String-Presence — Kommentar-Erwaehnungen (z. B. compareMetricDefs.ts:4)
// sind kein produktiver Verweis.

import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const SRC_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', '..');

const IMPORT_RE = /from\s+['"][^'"]*(CompareMatrix|HourlyMatrix)\.svelte['"]/;

function collectSourceFiles(dir: string, out: string[] = []): string[] {
	for (const entry of readdirSync(dir)) {
		const full = join(dir, entry);
		if (statSync(full).isDirectory()) {
			if (entry === '__tests__' || entry === 'node_modules') continue;
			collectSourceFiles(full, out);
		} else if (/\.(svelte|ts)$/.test(entry) && !/\.test\.ts$/.test(entry)) {
			// Die beiden Totcode-Dateien selbst zaehlen nicht als Verweis.
			if (/(CompareMatrix|HourlyMatrix)\.svelte$/.test(entry)) continue;
			out.push(full);
		}
	}
	return out;
}

describe('AC-20: CompareMatrix/HourlyMatrix bleiben unverdrahteter Totcode', () => {
	test('kein produktiver Import ausserhalb von __tests__/', () => {
		const offenders = collectSourceFiles(SRC_ROOT).filter((f) =>
			IMPORT_RE.test(readFileSync(f, 'utf-8'))
		);
		assert.deepStrictEqual(
			offenders,
			[],
			`Produktive Importe der Ranking-Totcode-Komponenten gefunden:\n${offenders.join('\n')}`
		);
	});
});
