// doc-compliance-test
//
// TDD RED — Scheibe D2 von #1301 (#1292 P4): eine Bedienstelle je Editor für
// „Amtliche Warnungen im Bericht". STRUKTURELLE Invariante via Source-Inspektion,
// weil Svelte-5-Komponenten in diesem Setup nicht mountbar sind (kein
// @testing-library/svelte). Der End-to-End-Klick-Nachweis läuft in der
// Staging-E2E (Playwright, Phase 6).
//
// Geprüft:
//  - Der geteilte Alarm-Tab (route + vergleich) rendert NUR noch den Auslöser-
//    Schalter, NICHT mehr den Inhalt-Schalter (Testid entfällt).
//  - Die Inhalt-Heimaten (Trip WeatherMetricsTab, Vergleich CompareInhaltSection)
//    tragen das geschärfte Label „Amtliche Warnungen im Bericht".
//
// Spec: docs/specs/modules/d2_1301_official_alerts_single_control.md (AC-1, AC-3)
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/official_alerts_single_control_ui.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
// __tests__ -> shared
const SHARED_DIR = join(here, '..');
// __tests__ -> shared -> components -> lib
const LIB_COMPONENTS = join(here, '..', '..');

const ALARME_TAB = join(SHARED_DIR, 'AlarmeTab.svelte');
const COMPARE_INHALT = join(LIB_COMPONENTS, 'compare', 'CompareInhaltSection.svelte');
const WEATHER_METRICS_TAB = join(SHARED_DIR, 'WeatherMetricsTab.svelte');

const CONTENT_TOGGLE_TESTID = 'alerts-tab-official-alerts-toggle';
const TRIGGER_TOGGLE_TESTID = 'alerts-tab-official-alert-triggers-toggle';
const CONTENT_LABEL = 'Amtliche Warnungen im Bericht';

function read(path: string): string {
	return readFileSync(path, 'utf-8');
}

describe('D2 AC-1: Alarm-Tab hat nur noch den Auslöser-Schalter', () => {
	test('AlarmeTab enthält NICHT mehr die Inhalt-Bedienstelle (Testid entfällt)', () => {
		const src = read(ALARME_TAB);
		assert.ok(
			!src.includes(CONTENT_TOGGLE_TESTID),
			`AlarmeTab darf den Inhalt-Schalter (testid "${CONTENT_TOGGLE_TESTID}") nicht ` +
				'mehr rendern — er ist der doppelte Schalter (D2).'
		);
	});

	test('AlarmeTab behält den Auslöser-Schalter „lösen Alert aus"', () => {
		const src = read(ALARME_TAB);
		assert.ok(
			src.includes(TRIGGER_TOGGLE_TESTID),
			`AlarmeTab muss den Auslöser-Schalter (testid "${TRIGGER_TOGGLE_TESTID}") behalten.`
		);
	});

	test('AlarmeTab schreibt official_alerts_enabled nicht mehr über die konsolidierte Payload', () => {
		const src = read(ALARME_TAB);
		assert.ok(
			!src.includes('officialAlertsEnabled'),
			'AlarmeTab darf officialAlertsEnabled weder halten noch in die Payload geben (D2).'
		);
	});
});

describe('D2 AC-3: Inhalt-Heimaten tragen das geschärfte Label', () => {
	test('CompareInhaltSection zeigt „Amtliche Warnungen im Bericht"', () => {
		const src = read(COMPARE_INHALT);
		assert.ok(
			src.includes(CONTENT_LABEL),
			`CompareInhaltSection muss das Label „${CONTENT_LABEL}" tragen (Unterscheidung ` +
				'zum Alarm-Auslöser).'
		);
	});

	test('WeatherMetricsTab (Trip-Inhalt) zeigt „Amtliche Warnungen im Bericht"', () => {
		const src = read(WEATHER_METRICS_TAB);
		assert.ok(
			src.includes(CONTENT_LABEL),
			`WeatherMetricsTab muss das Label „${CONTENT_LABEL}" tragen (Unterscheidung ` +
				'zum Alarm-Auslöser).'
		);
	});
});
