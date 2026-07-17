// TDD RED — Issue #1286: EditReportConfigSection rendert den Zeitplan nicht
// mehr selbst, sondern die geteilte VTSchedulePlan (context=route). Damit ist
// VTSchedulePlan die EINZIGE Zeitplan-UI-Quelle (Teilungs-Invariante,
// CLAUDE.md). Spec AC-1/AC-10.
//
// RED-Erwartung: EditReportConfigSection.svelte importiert VTSchedulePlan
// noch nicht und trägt noch eigenes report-morning-time-Markup — schlägt
// fehl bis Phase 6.
//
// Source-Inspection-Test (kein DOM-Rendering, keine Mocks, kein Playwright —
// Praezedenz: vt_schedule_plan_hour_step.test.ts). Svelte-5-Komponenten sind
// ohne @testing-library/svelte (nicht in package.json) in diesem
// Test-Setup nicht mountbar.
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
const EDIT_REPORT_CONFIG = join(here, '..', 'EditReportConfigSection.svelte');
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

describe('AC-1/AC-10: EditReportConfigSection nutzt die geteilte VTSchedulePlan statt eigenem Markup', () => {
	test('EditReportConfigSection.svelte importiert VTSchedulePlan aus versand-tab/', () => {
		const src = readFileSync(EDIT_REPORT_CONFIG, 'utf-8');
		assert.ok(
			/import VTSchedulePlan from ['"].*versand-tab\/VTSchedulePlan\.svelte['"]/.test(src),
			'EditReportConfigSection.svelte muss VTSchedulePlan aus versand-tab/VTSchedulePlan.svelte importieren'
		);
	});

	test('EditReportConfigSection.svelte verwendet <VTSchedulePlan context="route" ...>', () => {
		const src = readFileSync(EDIT_REPORT_CONFIG, 'utf-8');
		assert.ok(
			src.includes('<VTSchedulePlan context="route"'),
			'EditReportConfigSection.svelte muss <VTSchedulePlan context="route" ...> rendern'
		);
	});

	test('EditReportConfigSection.svelte traegt KEIN eigenes report-morning-time-Markup mehr', () => {
		const src = readFileSync(EDIT_REPORT_CONFIG, 'utf-8');
		assert.ok(
			!src.includes('data-testid="report-morning-time"'),
			'EditReportConfigSection.svelte darf data-testid="report-morning-time" nicht mehr selbst rendern'
		);
	});

	test('EditReportConfigSection.svelte traegt KEIN eigenes report-evening-time-Markup mehr', () => {
		const src = readFileSync(EDIT_REPORT_CONFIG, 'utf-8');
		assert.ok(
			!src.includes('data-testid="report-evening-time"'),
			'EditReportConfigSection.svelte darf data-testid="report-evening-time" nicht mehr selbst rendern'
		);
	});

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
