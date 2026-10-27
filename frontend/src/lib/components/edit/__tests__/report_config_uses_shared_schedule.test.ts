// Issue #1286 AC-10 (Maintainability): VTSchedulePlan ist die EINZIGE Zeitplan-UI-Quelle
// (Teilungs-Invariante, CLAUDE.md). Issue #2277 S5: die Section-Faelle entfallen, weil
// die alte Report-Config-Section entfernt wurde (Zusicherung entfaellt, weil Code entfaellt);
// die Einzigkeit der Testids bleibt gueltig und wird weiter geprueft.
//
// Source-Inspection-Test (kein DOM-Rendering, keine Mocks).
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/edit/__tests__/report_config_uses_shared_schedule.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, basename } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
// frontend/src
const SRC_ROOT = join(here, '..', '..', '..', '..');

/** Rekursiv alle .svelte-Dateien unter root sammeln (kein Shell-grep). */
function findSvelteFiles(root: string): string[] {
	const out: string[] = [];
	for (const entry of readdirSync(root)) {
		if (entry === 'node_modules' || entry === '.svelte-kit') continue;
		const full = join(root, entry);
		const st = statSync(full);
		if (st.isDirectory()) {
			out.push(...findSvelteFiles(full));
		} else if (entry.endsWith('.svelte')) {
			out.push(full);
		}
	}
	return out;
}

describe('AC-10: VTSchedulePlan ist die einzige Quelle der Zeitplan-Testids', () => {
	test('AC-10 Maintainability: genau EINE .svelte-Datei traegt report-morning-time — VTSchedulePlan.svelte', () => {
		const files = findSvelteFiles(SRC_ROOT);
		const hits = files.filter((f) => readFileSync(f, 'utf-8').includes('data-testid="report-morning-time"'));
		assert.equal(
			hits.length,
			1,
			`Es darf genau EINE .svelte-Datei mit data-testid="report-morning-time" geben (eine Quelle), gefunden:\n${hits.join('\n')}`
		);
		assert.equal(
			basename(hits[0] ?? ''),
			'VTSchedulePlan.svelte',
			`Die einzige Quelle fuer report-morning-time muss VTSchedulePlan.svelte sein, gefunden: ${hits[0]}`
		);
	});

	test('AC-10 Maintainability: genau EINE .svelte-Datei traegt report-evening-time — VTSchedulePlan.svelte', () => {
		const files = findSvelteFiles(SRC_ROOT);
		const hits = files.filter((f) => readFileSync(f, 'utf-8').includes('data-testid="report-evening-time"'));
		assert.equal(
			hits.length,
			1,
			`Es darf genau EINE .svelte-Datei mit data-testid="report-evening-time" geben (eine Quelle), gefunden:\n${hits.join('\n')}`
		);
		assert.equal(
			basename(hits[0] ?? ''),
			'VTSchedulePlan.svelte',
			`Die einzige Quelle fuer report-evening-time muss VTSchedulePlan.svelte sein, gefunden: ${hits[0]}`
		);
	});
});
