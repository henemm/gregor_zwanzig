// TDD RED — Issue #430 + #431: WizardState-Erweiterungen für 5-Step-Wizard +
// Layout-Editor. SPEC: docs/specs/modules/issue_430_431_wizard_layout_step.md.
// TEST-MANIFEST: docs/specs/tests/issue_430_431_wizard_layout_step_tests.md.
//
// Source-Inspection-Tests (analog WeatherMetricsMobileView.test.ts) — Plain-
// Node-Loader kann `$lib`-Aliases in `wizardState.svelte.ts` nicht resolven,
// daher prüfen wir die Erweiterungen direkt am .ts-Source:
//   - currentStep akzeptiert Werte 1..5 (Typ-Literal-Union erweitert)
//   - nextStep/prevStep mit Grenze 5 statt 4
//   - Neue Getter canAdvanceStep4 (Layout, true) + canAdvanceStep5 (Reports)
//   - canAdvanceCurrent-Switch erweitert um Fall 5
//   - Neues Feld channelLayouts (Default null)
//   - toTripPayload() schreibt display_config.channel_layouts wenn gesetzt
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/issue_430_431_wizard_state.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const STATE_FILE = join(here, '..', 'wizardState.svelte.ts');

function read(): string { return readFileSync(STATE_FILE, 'utf-8'); }

// =============================================================================
// AC-4: currentStep akzeptiert Werte 1..5
// =============================================================================

test('AC-4: currentStep-Type-Literal-Union erweitert auf 1|2|3|4|5', () => {
	const src = read();
	// Heute: `currentStep = $state<1 | 2 | 3 | 4>(1);`
	// Soll:  `currentStep = $state<1 | 2 | 3 | 4 | 5>(1);`
	const has5 = /currentStep\s*=\s*\$state\s*<\s*1\s*\|\s*2\s*\|\s*3\s*\|\s*4\s*\|\s*5\s*>/.test(src);
	assert.ok(
		has5,
		'currentStep-Typ muss 1|2|3|4|5 sein (heute: 1|2|3|4)',
	);
});

// =============================================================================
// AC-5: nextStep / prevStep mit Grenze 5 statt 4
// =============================================================================

test('AC-5: nextStep verwendet Grenze 5 (kein Overflow über 5)', () => {
	const src = read();
	// Wir suchen die nextStep-Implementierung — sie muss `< 5` enthalten
	// (und entsprechend `(this.currentStep + 1) as 1 | 2 | 3 | 4 | 5`).
	const nextStepMatch = src.match(/nextStep\s*\([^)]*\)\s*:\s*void\s*\{[\s\S]*?\n\t\}/);
	assert.ok(nextStepMatch, 'nextStep-Methode muss vorhanden sein');
	const body = nextStepMatch![0];
	assert.ok(
		/this\.currentStep\s*<\s*5/.test(body),
		'nextStep muss `this.currentStep < 5` verwenden (heute: < 4)',
	);
});

test('AC-5: prevStep verwendet Cast auf 1|2|3|4|5', () => {
	const src = read();
	const prevStepMatch = src.match(/prevStep\s*\([^)]*\)\s*:\s*void\s*\{[\s\S]*?\n\t\}/);
	assert.ok(prevStepMatch, 'prevStep-Methode muss vorhanden sein');
	const body = prevStepMatch![0];
	// Cast muss 5 erlauben
	assert.ok(
		/as\s+1\s*\|\s*2\s*\|\s*3\s*\|\s*4\s*\|\s*5/.test(body),
		'prevStep-Cast muss `as 1 | 2 | 3 | 4 | 5` sein',
	);
});

// =============================================================================
// AC-4 (Plumbing): canAdvanceStep4 + canAdvanceStep5
// =============================================================================

test('AC-4: Neuer Getter canAdvanceStep4 existiert (Layout-Step)', () => {
	const src = read();
	const has = /get\s+canAdvanceStep4\s*\(\s*\)\s*:\s*boolean/.test(src);
	assert.ok(has, 'Getter canAdvanceStep4 (Layout) muss existieren');
});

test('AC-4: Neuer Getter canAdvanceStep5 existiert (Reports-Step)', () => {
	const src = read();
	const has = /get\s+canAdvanceStep5\s*\(\s*\)\s*:\s*boolean/.test(src);
	assert.ok(has, 'Getter canAdvanceStep5 (Reports) muss existieren');
});

test('AC-4: canAdvanceCurrent-Switch hat Fall 5', () => {
	const src = read();
	// Im aktuellen Source: case 4 → canAdvanceStep4. Soll: case 5 → canAdvanceStep5.
	const has = /case\s+5\s*:\s*[\s\S]{0,80}canAdvanceStep5/.test(src);
	assert.ok(
		has,
		'canAdvanceCurrent-Switch muss case 5 → canAdvanceStep5 enthalten',
	);
});

// =============================================================================
// AC-4 (Save-Pipeline): channelLayouts-Feld
// =============================================================================

test('AC-4: Neues Feld channelLayouts vorhanden (Default null)', () => {
	const src = read();
	// Soll: `channelLayouts = $state<ChannelLayouts | null>(null);`
	const has = /channelLayouts\s*=\s*\$state\s*<[^>]*>\s*\(\s*null\s*\)/.test(src);
	assert.ok(
		has,
		'channelLayouts muss als $state<... | null>(null) deklariert sein',
	);
});

// =============================================================================
// AC-11: toTripPayload() schreibt channel_layouts wenn gesetzt
// =============================================================================

test('AC-11: toTripPayload() schreibt channel_layouts unter display_config', () => {
	const src = read();
	// Suchen nach Zuweisung: trip.display_config = { ..., channel_layouts: ... }
	// ODER: trip.display_config.channel_layouts = ...
	const has = /channel_layouts/.test(src) && /toTripPayload/.test(src);
	assert.ok(
		has,
		'toTripPayload() muss channel_layouts in display_config schreiben',
	);

	// Stärker: Im toTripPayload-Block muss der channelLayouts-State referenziert sein
	const payloadMatch = src.match(/toTripPayload\s*\([^)]*\)\s*:\s*Trip\s*\{[\s\S]*?\n\t\}/);
	assert.ok(payloadMatch, 'toTripPayload-Methode muss vorhanden sein');
	const body = payloadMatch![0];
	assert.ok(
		/this\.channelLayouts/.test(body),
		'toTripPayload() muss this.channelLayouts referenzieren',
	);
	assert.ok(
		/channel_layouts/.test(body),
		'toTripPayload() muss den snake_case "channel_layouts"-Key schreiben',
	);
});

test('AC-11: toTripPayload() omittet channel_layouts bei null (omitempty-Symmetrie)', () => {
	const src = read();
	const payloadMatch = src.match(/toTripPayload\s*\([^)]*\)\s*:\s*Trip\s*\{[\s\S]*?\n\t\}/);
	assert.ok(payloadMatch);
	const body = payloadMatch![0];
	// Wir suchen einen if-Guard, der null oder length-Check macht
	const hasGuard = /if\s*\(\s*this\.channelLayouts\b|if\s*\(\s*this\.channelLayouts\s*!==\s*null/.test(body);
	assert.ok(
		hasGuard,
		'toTripPayload() braucht einen null-Guard für channelLayouts (Spec: nur schreiben wenn nicht null)',
	);
});
