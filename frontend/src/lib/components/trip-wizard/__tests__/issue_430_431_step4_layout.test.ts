// TDD RED — Issue #431: Step4Layout (Wizard) + WeatherMetricsTab-Regression.
// SPEC: docs/specs/modules/issue_430_431_wizard_layout_step.md (AC-7, AC-9, AC-10, AC-13, AC-15).
// TEST-MANIFEST: docs/specs/tests/issue_430_431_wizard_layout_step_tests.md.
//
// Source-Inspection-Tests:
//   - Step4Layout.svelte existiert mit 4 Channel-Tabs
//   - Step4Layout importiert ChannelPreviewBlock
//   - Step4Layout bindet pro Kanal an wizard.channelLayouts
//   - WeatherMetricsTab importiert OutputLayoutEditor (Wrapper-Pattern)
//   - WeatherMetricsTab behält Save-Button
//   - TripWizardShell mountet Step4Layout bei currentStep===4
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/issue_430_431_step4_layout.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const STEP4_LAYOUT = join(here, '..', 'steps', 'Step4Layout.svelte');
const SHELL        = join(here, '..', 'TripWizardShell.svelte');
const WEATHER_TAB  = join(here, '..', '..', 'trip-detail', 'WeatherMetricsTab.svelte');

function read(p: string): string { return readFileSync(p, 'utf-8'); }

// =============================================================================
// AC-7: Step4Layout existiert + 4 Channel-Tabs
// =============================================================================

test('AC-7: Step4Layout.svelte existiert unter steps/', () => {
	assert.ok(existsSync(STEP4_LAYOUT), `Step4Layout.svelte fehlt: ${STEP4_LAYOUT}`);
});

// #610: Signal entfernt — nur noch 3 Kanäle
test('AC-7 #610: Step4Layout enthält Email/Telegram/SMS (kein Signal)', () => {
	const src = read(STEP4_LAYOUT);
	for (const ch of ['email', 'telegram', 'sms']) {
		assert.ok(
			src.includes(`'${ch}'`) || src.includes(`"${ch}"`),
			`Step4Layout sollte den Channel-Identifier '${ch}' enthalten.`,
		);
	}
	assert.ok(
		!src.includes("'signal'") && !src.includes('"signal"'),
		'Step4Layout darf nach #610 keinen signal-Channel-Identifier mehr enthalten',
	);
});

// =============================================================================
// AC-10: Step4Layout importiert ChannelPreviewBlock
// =============================================================================

test('AC-10: Step4Layout importiert ChannelPreviewBlock', () => {
	const src = read(STEP4_LAYOUT);
	assert.ok(
		src.includes('ChannelPreviewBlock'),
		'Step4Layout muss ChannelPreviewBlock importieren oder verwenden.',
	);
});

// =============================================================================
// AC-9: Step4Layout bindet an wizard.channelLayouts pro Kanal
// =============================================================================

test('AC-9: Step4Layout referenziert wizard.channelLayouts (per-Channel-State-Sync)', () => {
	const src = read(STEP4_LAYOUT);
	assert.ok(
		src.includes('channelLayouts'),
		'Step4Layout muss wizard.channelLayouts referenzieren, um pro Kanal eigene Buckets zu halten.',
	);
});

// =============================================================================
// AC-13: WeatherMetricsTab importiert OutputLayoutEditor (Wrapper-Pattern)
// =============================================================================

test('AC-13: WeatherMetricsTab importiert OutputLayoutEditor', () => {
	const src = read(WEATHER_TAB);
	assert.ok(
		src.includes('OutputLayoutEditor'),
		'WeatherMetricsTab muss OutputLayoutEditor importieren (Wrapper-Pattern).',
	);
});

test('AC-13: WeatherMetricsTab behält Save-Button (weather-metrics-tab-save)', () => {
	const src = read(WEATHER_TAB);
	assert.ok(
		src.includes('weather-metrics-tab-save'),
		'WeatherMetricsTab muss seinen Save-Button (testid "weather-metrics-tab-save") behalten.',
	);
});

// =============================================================================
// AC-15: TripWizardShell mountet Step4Layout bei currentStep===4
// =============================================================================

test('AC-15: TripWizardShell importiert Step4Layout', () => {
	const src = read(SHELL);
	assert.ok(
		src.includes('Step4Layout'),
		'TripWizardShell muss Step4Layout importieren.',
	);
});

test('AC-15: TripWizardShell mountet Step4Layout bei currentStep === 4', () => {
	const src = read(SHELL);
	// Heutige Shell hat currentStep === 4 → Step4Reports. Nach #430+#431 →
	// currentStep === 4 → Step4Layout, currentStep === 5 → Step4Reports/Step5Reports.
	const has = /currentStep\s*===\s*4[\s\S]{0,100}Step4Layout/.test(src);
	assert.ok(
		has,
		'TripWizardShell muss bei currentStep === 4 die Step4Layout-Komponente rendern.',
	);
});

test('AC-15: TripWizardShell mountet Reports-Komponente bei currentStep === 5', () => {
	const src = read(SHELL);
	// Reports-Komponente kann Step4Reports.svelte oder Step5Reports.svelte heißen
	// (Datei-Umbenennung ist OOS für diese PR — PR 4 macht das).
	const has = /currentStep\s*===\s*5[\s\S]{0,200}(Step4Reports|Step5Reports)/.test(src);
	assert.ok(
		has,
		'TripWizardShell muss bei currentStep === 5 die Reports-Komponente (Step4Reports oder Step5Reports) rendern.',
	);
});
