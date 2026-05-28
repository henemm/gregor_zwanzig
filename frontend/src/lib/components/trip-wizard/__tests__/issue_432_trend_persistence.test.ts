// TDD RED — Issue #432 Scope-Erweiterung (schließt #437): Trend-Persistenz.
// SPEC: docs/specs/modules/issue_432_step3_step5_polish.md (AC-16..AC-19).
//
// Nach GREEN-Iteration 2:
//   - WizardState hat trendEnabled-Feld mit Default true
//   - toTripPayload schreibt rc.multi_day_trend_evening = this.trendEnabled
//   - Step5Reports bindet bind:checked={wizard.trendEnabled}
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/issue_432_trend_persistence.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const STATE_FILE = join(here, '..', 'wizardState.svelte.ts');
const STEP5 = join(here, '..', 'steps', 'Step5Reports.svelte');

function readState(): string { return readFileSync(STATE_FILE, 'utf-8'); }
function readStep5(): string { return readFileSync(STEP5, 'utf-8'); }

// AC-16: trendEnabled-Feld mit Default true
test('AC-16: WizardState enthält trendEnabled-Feld als $state mit Default true', () => {
	const src = readState();
	const has = /trendEnabled\s*=\s*\$state\s*(<[^>]*>)?\s*\(\s*true\s*\)/.test(src);
	assert.ok(has, 'WizardState muss trendEnabled als $state mit Default true deklarieren');
});

// AC-16: toTripPayload schreibt multi_day_trend_evening
test('AC-16: toTripPayload schreibt rc.multi_day_trend_evening aus this.trendEnabled', () => {
	const src = readState();
	const payloadMatch = src.match(/toTripPayload\s*\([^)]*\)\s*:\s*Trip\s*\{[\s\S]*?\n\t\}/);
	assert.ok(payloadMatch, 'toTripPayload-Methode muss vorhanden sein');
	const body = payloadMatch![0];
	assert.ok(/multi_day_trend_evening/.test(body), 'toTripPayload muss multi_day_trend_evening schreiben');
	assert.ok(/this\.trendEnabled/.test(body), 'toTripPayload muss this.trendEnabled referenzieren');
});

// AC-19: Step5Reports bind:checked an wizard.trendEnabled
test('AC-19: Step5Reports bindet evening-trend-toggle an wizard.trendEnabled', () => {
	const src = readStep5();
	const hasBind = /bind:checked\s*=\s*\{\s*wizard\.trendEnabled\s*\}/.test(src);
	assert.ok(hasBind, 'Step5Reports muss bind:checked={wizard.trendEnabled} haben');
});

test('AC-19: Step5Reports nutzt KEINEN lokalen $state für trendEnabled', () => {
	const src = readStep5();
	const hasLocal = /let\s+trendEnabled\s*=\s*\$state/.test(src);
	assert.ok(!hasLocal, 'Step5Reports darf trendEnabled nicht als lokalen $state halten');
});

// AC-18: Default true (BC)
test('AC-18: trendEnabled Default true (BC zu Backend multi_day_trend_reports=["evening"])', () => {
	const src = readState();
	const has = /trendEnabled\s*=\s*\$state\s*(<[^>]*>)?\s*\(\s*true\s*\)/.test(src);
	assert.ok(has, 'trendEnabled muss Default true sein');
});
