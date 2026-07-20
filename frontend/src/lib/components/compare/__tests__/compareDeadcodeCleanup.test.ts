// TDD RED — Epic #1301 Scheibe F3 (#1206): tote Compare-Komponenten löschen.
// SPEC: docs/specs/modules/feat_1301_f3_deadcode_offscreen.md (AC-1, AC-2, AC-3)
//
// Prüft via Source-Inspection (node:test + readFileSync/existsSync), dass die
// drei referenzlos gewordenen Dateien gelöscht sind und issue_462.test.ts
// keinen Eintrag mehr für die gelöschte SavePresetDialog.svelte trägt.
// Muster/Format: issue_683_wizard_remove.test.ts (F2b AC-1 Löschnachweis).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compareDeadcodeCleanup.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
// compare/ = __tests__/..
const COMPARE_DIR = join(here, '..');

// Löschziele dieser Scheibe (F3, #1206)
const SAVE_PRESET_DIALOG_FILE = join(COMPARE_DIR, 'SavePresetDialog.svelte');
const RANGE_SLIDER_FILE = join(COMPARE_DIR, 'RangeSlider.svelte');
const WEEKLY_SCHEDULER_TEST_FILE = join(here, 'issue_511_weekly_scheduler.test.ts');
const ISSUE_462_TEST_FILE = join(COMPARE_DIR, 'issue_462.test.ts');

// Repo-Root (6x up: __tests__ → compare → components → lib → src → frontend → repo-root)
const REPO_ROOT = join(here, '..', '..', '..', '..', '..', '..');
const SRC_DIR = join(REPO_ROOT, 'frontend', 'src');

// =============================================================================
// Hilfsfunktion: alle .svelte/.ts/.js-Dateien in frontend/src rekursiv sammeln
// =============================================================================

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

// =============================================================================
// AC-1: compare/SavePresetDialog.svelte (Alt-Editor-Dialog, referenzlos seit F2b)
// =============================================================================

test('AC-1: compare/SavePresetDialog.svelte wurde gelöscht', () => {
	assert.strictEqual(
		existsSync(SAVE_PRESET_DIALOG_FILE),
		false,
		`compare/SavePresetDialog.svelte muss gelöscht sein (Epic #1301 F3, #1206), existiert aber noch: ${SAVE_PRESET_DIALOG_FILE}`
	);
});

test('AC-1: Keine Produktionsdatei importiert compare/SavePresetDialog.svelte (Namensvetter shared/weather-metrics-tab/SavePresetDialog.svelte bleibt unberührt)', () => {
	const files = collectSourceFiles(SRC_DIR);
	const hits: string[] = [];
	for (const f of files) {
		if (f.endsWith('compareDeadcodeCleanup.test.ts')) continue;
		if (f.includes('__tests__') || f.includes('.test.ts') || f.includes('.test.js')) continue;
		if (f === SAVE_PRESET_DIALOG_FILE) continue;
		const content = readFileSync(f, 'utf-8');
		// Treffer nur, wenn die Datei SavePresetDialog.svelte referenziert UND
		// es sich NICHT um den unabhängigen Namensvetter in
		// shared/weather-metrics-tab/ handelt (Invarianz-Abgrenzung der Spec).
		if (content.includes('SavePresetDialog.svelte') && !content.includes('weather-metrics-tab')) {
			hits.push(f.replace(SRC_DIR + '/', ''));
		}
	}
	assert.deepStrictEqual(
		hits,
		[],
		`Folgende Produktionsdateien importieren noch compare/SavePresetDialog.svelte:\n  ${hits.join('\n  ')}`
	);
});

test('AC-1: issue_462.test.ts enthält keinen SavePresetDialog.svelte-MIGRATED_FILES-Eintrag mehr (Kommentar-Vermerk darf den Dateinamen weiterhin nennen)', () => {
	assert.ok(existsSync(ISSUE_462_TEST_FILE), `issue_462.test.ts fehlt: ${ISSUE_462_TEST_FILE}`);
	const src = readFileSync(ISSUE_462_TEST_FILE, 'utf-8');
	assert.strictEqual(
		/join\(COMPARE_DIR,\s*'SavePresetDialog\.svelte'\)/.test(src),
		false,
		"issue_462.test.ts darf nach der Löschung von compare/SavePresetDialog.svelte keinen MIGRATED_FILES-Eintrag join(COMPARE_DIR, 'SavePresetDialog.svelte') mehr enthalten (Spec Teil 1, Kommentar-Vermerk analog #1256)"
	);
});

// =============================================================================
// AC-2: compare/RangeSlider.svelte (referenzlos, kein Import, kein Test)
// =============================================================================

test('AC-2: compare/RangeSlider.svelte wurde gelöscht', () => {
	assert.strictEqual(
		existsSync(RANGE_SLIDER_FILE),
		false,
		`compare/RangeSlider.svelte muss gelöscht sein (Epic #1301 F3, #1206, referenzlos), existiert aber noch: ${RANGE_SLIDER_FILE}`
	);
});

test('AC-2: compare/RangeSlider.svelte ist referenzlos (Beweis vor/nach der Löschung — kein Import über frontend/src)', () => {
	const files = collectSourceFiles(SRC_DIR);
	const hits: string[] = [];
	for (const f of files) {
		if (f.endsWith('compareDeadcodeCleanup.test.ts')) continue;
		if (f === RANGE_SLIDER_FILE) continue;
		const content = readFileSync(f, 'utf-8');
		if (/RangeSlider/.test(content)) {
			hits.push(f.replace(SRC_DIR + '/', ''));
		}
	}
	assert.deepStrictEqual(
		hits,
		[],
		`Folgende Dateien referenzieren RangeSlider — Referenzlosigkeits-Annahme der Spec verletzt:\n  ${hits.join('\n  ')}`
	);
});

// =============================================================================
// AC-3: compare/__tests__/issue_511_weekly_scheduler.test.ts (obsoletes Verhalten,
// Wochenrhythmus mit #1232 Scheibe 2a produktiv entfernt)
// =============================================================================

test('AC-3: compare/__tests__/issue_511_weekly_scheduler.test.ts wurde gelöscht', () => {
	assert.strictEqual(
		existsSync(WEEKLY_SCHEDULER_TEST_FILE),
		false,
		`issue_511_weekly_scheduler.test.ts muss gelöscht sein (Epic #1301 F3, #1206 — prüft obsoleten Wochenrhythmus, #1232 Scheibe 2a), existiert aber noch: ${WEEKLY_SCHEDULER_TEST_FILE}`
	);
});
