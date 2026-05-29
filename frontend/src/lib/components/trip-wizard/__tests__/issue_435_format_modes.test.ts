// TDD RED — Issue #435 Metrik-Format-Modi (Frontend-Tests).
// SPEC: docs/specs/modules/issue_435_metric_format_modes.md (AC-2, AC-9).
//
// Diese Tests scheitern, weil:
//   - Step3Weather.svelte hat heute 4 hardcoded <option>-Tags und persistiert nur
//     use_friendly_format (Mapping mode !== 'raw' → bool). Es fehlt:
//       a) ein iteratives Rendern der Optionen aus metric.format_modes
//       b) das Schreiben eines format_mode-Strings in WeatherConfigMetric
//   - WeatherConfigDialog.svelte hat heute eine 2-Wege-Segmented-Control
//     mit hardkodierten Labels "Roh" / "Indikator". Es fehlt:
//       a) eine N-Optionen-Auswahl aus metric.format_modes
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-wizard/__tests__/issue_435_format_modes.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const STEP3 = join(here, '..', 'steps', 'Step3Weather.svelte');
const DIALOG = join(here, '..', '..', 'WeatherConfigDialog.svelte');

function readStep3(): string {
	return readFileSync(STEP3, 'utf-8');
}
function readDialog(): string {
	return readFileSync(DIALOG, 'utf-8');
}

// -----------------------------------------------------------------------------
// AC-2: Wizard-Dropdown filtert auf erlaubte Modi pro Metrik
// -----------------------------------------------------------------------------

test('AC-2: Step3Weather rendert <option>-Liste NICHT mehr als 4er-Hartblock', () => {
	const src = readStep3();
	// RED-Trigger: heute existiert eine statische Sequenz aller 4 Optionen.
	// Wir suchen die EXAKTE Hartkodierung im SOLL nicht mehr vor.
	const hardBlock =
		/<option\s+value="raw">Roh<\/option>\s*<option\s+value="scale">Skala<\/option>\s*<option\s+value="simplified">Vereinfacht<\/option>\s*<option\s+value="symbol">Symbol<\/option>/;
	assert.ok(
		!hardBlock.test(src),
		'AC-2 RED: Step3Weather darf die 4 Optionen nicht mehr hartkodiert als Block enthalten — sie müssen aus metric.format_modes iteriert werden.'
	);
});

test('AC-2: Step3Weather iteriert Format-Optionen über metric.format_modes', () => {
	const src = readStep3();
	// Erwarte irgendwo eine #each-Iteration oder einen Verweis auf
	// `m.format_modes` / `metric.format_modes` als Datenquelle für die <option>s.
	const hasFormatModesIteration =
		/\{#each\s+[^}]*\.format_modes[^}]*\}/.test(src) ||
		/\bm\.format_modes\b/.test(src) ||
		/\bmetric\.format_modes\b/.test(src);
	assert.ok(
		hasFormatModesIteration,
		'AC-2 RED: Step3Weather muss die Format-Optionen aus metric.format_modes iterieren (heute hardcoded 4 Optionen).'
	);
});

test('AC-2: Step3Weather persistiert format_mode in WeatherConfigMetric', () => {
	const src = readStep3();
	// Heute: `m.use_friendly_format = mode !== 'raw';`
	// SOLL: zusätzlich `m.format_mode = mode;`
	const writesFormatMode = /\bm\.format_mode\s*=\s*mode\b/.test(src) ||
		/\bm\.format_mode\s*=\s*\(/.test(src) ||
		/\.format_mode\s*=\s*[^=]/.test(src);
	assert.ok(
		writesFormatMode,
		'AC-2 RED: Step3Weather muss format_mode als String in WeatherConfigMetric persistieren (heute nur use_friendly_format).'
	);
});

// -----------------------------------------------------------------------------
// AC-9: WeatherConfigDialog N-Optionen-Dropdown statt 2er Segmented-Control
// -----------------------------------------------------------------------------

test('AC-9: WeatherConfigDialog enthält KEINE 2er-Roh/Indikator-Segmented-Control mehr', () => {
	const src = readDialog();
	// RED-Trigger: heute existiert exakt diese 2-Optionen-Konfiguration.
	const twoWaySegmented =
		/options\s*=\s*\{\s*\[\s*\{\s*value:\s*['"]raw['"]\s*,\s*label:\s*['"]Roh['"]\s*\}\s*,\s*\{\s*value:\s*['"]indicator['"]\s*,\s*label:\s*['"]Indikator['"]\s*\}\s*\]\s*\}/;
	assert.ok(
		!twoWaySegmented.test(src),
		'AC-9 RED: WeatherConfigDialog darf die 2-Wege-Segmented-Control "Roh/Indikator" nicht mehr enthalten — sie muss durch eine N-Optionen-Auswahl aus metric.format_modes ersetzt werden.'
	);
});

test('AC-9: WeatherConfigDialog iteriert oder referenziert metric.format_modes', () => {
	const src = readDialog();
	const referencesFormatModes =
		/\bmetric\.format_modes\b/.test(src) ||
		/\bm\.format_modes\b/.test(src) ||
		/\{#each\s+[^}]*format_modes[^}]*\}/.test(src);
	assert.ok(
		referencesFormatModes,
		'AC-9 RED: WeatherConfigDialog muss metric.format_modes als Quelle der Auswahl-Optionen referenzieren (heute hardcoded "Roh"/"Indikator").'
	);
});

test('AC-9: WeatherConfigDialog persistiert format_mode (nicht nur use_friendly_format)', () => {
	const src = readDialog();
	const writesFormatMode = /\bformat_mode\b/.test(src);
	assert.ok(
		writesFormatMode,
		'AC-9 RED: WeatherConfigDialog muss format_mode als String führen (heute nur use_friendly_format boolean).'
	);
});
