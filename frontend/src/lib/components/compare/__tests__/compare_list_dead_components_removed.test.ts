// TDD RED — Issue #1256 Scheibe 1: Alt-Komponenten-Entfernung (AC-3).
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md (AC-3)
// Verifiziert in der Spec-Phase (Zeilen 303-305): LocationsRail.svelte,
// AutoReportsOverview.svelte, AutoReportCard.svelte (compare/) haben
// KEINEN produktiven Import außerhalb ihrer eigenen Testdateien — Totcode,
// das Scheibe 1 löscht.
//
// RED-Erwartung: die drei Dateien existieren im Ist noch → alle
// Existenz-Tests hier schlagen fehl, bis sie gelöscht sind. Der
// Import-Regressionstest ist bereits im Ist grün (kein produktiver Import
// heute nachweisbar), bleibt aber als Regressionsschutz erhalten.
//
// Bekannte Nebenwirkung (siehe Entwickler-Bericht): drei WEITERE
// Test-Dateien lesen den Quelltext dieser drei Komponenten direkt
// (readFileSync) und brechen daher beim Löschen, sind aber NICHT Teil der
// Scheibe-1-Dateiliste der Spec:
//   - frontend/src/lib/components/compare/issue_462.test.ts
//     (liegt außerhalb __tests__/, prüft Atom-Importe von AutoReportCard/
//     AutoReportsOverview/LocationsRail)
//   - frontend/src/lib/components/compare/__tests__/issue_390_atomic_migration.test.ts
//     (PAGE_LOCAL_COMPOSITES-Block prüft AutoReportsOverview.svelte-Existenz)
//   - frontend/src/lib/components/compare/__tests__/issue_453_locations_rail.test.ts
//     (prüft LocationsRail.svelte-Quelltext direkt)
// Diese drei Dateien sind reine Testdateien (keine produktiven Importe im
// Sinne von AC-3), fallen daher nicht unter den in AC-3 geprüften
// "produktiver Import"-Begriff — sie werden aber beim Löschen der drei
// Alt-Komponenten in der GREEN-Phase mit-brechen und müssen dort ebenfalls
// angepasst/gelöscht werden (nicht Scope dieses RED-Tests).
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_list_dead_components_removed.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
// compare/__tests__ -> compare
const COMPARE_DIR = join(here, '..');
// compare/__tests__ -> compare -> components -> lib -> src
const SRC_DIR = join(here, '..', '..', '..', '..');

const DEAD_FILES = [
	join(COMPARE_DIR, 'LocationsRail.svelte'),
	join(COMPARE_DIR, 'AutoReportsOverview.svelte'),
	join(COMPARE_DIR, 'AutoReportCard.svelte'),
];

function collectSourceFiles(dir: string): string[] {
	const results: string[] = [];
	if (!existsSync(dir)) return results;
	for (const entry of readdirSync(dir)) {
		const full = join(dir, entry);
		const st = statSync(full);
		if (st.isDirectory()) {
			results.push(...collectSourceFiles(full));
		} else if (/\.(svelte|ts|js)$/.test(entry)) {
			results.push(full);
		}
	}
	return results;
}

for (const filePath of DEAD_FILES) {
	const name = filePath.split('/').pop();
	test(`AC-3: ${name} wurde gelöscht`, () => {
		assert.strictEqual(
			existsSync(filePath),
			false,
			`${name} muss gelöscht sein (verifizierter Totcode, Spec Zeilen 303-305), existiert aber noch: ${filePath}`
		);
	});
}

test('AC-3: keine produktive Datei importiert LocationsRail/AutoReportsOverview/AutoReportCard', () => {
	const files = collectSourceFiles(SRC_DIR);
	const names = DEAD_FILES.map((f) => f.split('/').pop()!.replace('.svelte', ''));
	const hits: string[] = [];
	for (const f of files) {
		// Diese Test-Datei selbst überspringen
		if (f.endsWith('compare_list_dead_components_removed.test.ts')) continue;
		// Alle Testdateien überspringen (AC-3: nur "produktiver" Import zählt)
		if (f.includes('__tests__') || f.includes('.test.ts') || f.includes('.test.js')) continue;
		// Die drei Alt-Dateien selbst überspringen (werden gelöscht, kein Selbst-Treffer)
		if (DEAD_FILES.includes(f)) continue;
		const content = readFileSync(f, 'utf-8');
		for (const name of names) {
			const hasImport = new RegExp(`import[^;]*${name}(\\.svelte)?`).test(content);
			const hasTag = new RegExp(`<${name}[\\s/>]`).test(content);
			if (hasImport || hasTag) {
				hits.push(`${f.replace(SRC_DIR + '/', '')}: ${name}`);
			}
		}
	}
	assert.deepStrictEqual(
		hits,
		[],
		`Folgende Produktionsdateien referenzieren noch Alt-Komponenten:\n  ${hits.join('\n  ')}`
	);
});
