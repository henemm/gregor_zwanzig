// TDD RED — Issue #587: Design-Fidelity Metrics-Editor
//
// Spec: docs/specs/modules/issue_587_metrics_editor_fidelity.md
//
// Source-Inspection-Tests: Prüfen, dass NEUE Muster vorhanden und ALTE entfernt sind.
// Vor der Implementierung scheitern AC-1 und AC-2 Tests (RED).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/issue_587_metrics_editor_fidelity.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const ROOT = fileURLToPath(new URL('../../../..', import.meta.url)); // -> frontend root

function readFrontend(relPath: string): string {
	return readFileSync(join(ROOT, 'src', relPath), 'utf-8');
}

// =============================================================================
// AC-1: TablePreview in WeatherMetricsTab eingebunden
// =============================================================================

test('AC-1a: WeatherMetricsTab importiert TablePreview', () => {
	const src = readFrontend('lib/components/trip-detail/WeatherMetricsTab.svelte');
	assert.equal(
		src.includes("import TablePreview") || src.includes("TablePreview from"),
		true,
		'WeatherMetricsTab.svelte muss TablePreview importieren'
	);
});

test('AC-1b: WeatherMetricsTab enthält <TablePreview im Template', () => {
	const src = readFrontend('lib/components/trip-detail/WeatherMetricsTab.svelte');
	assert.equal(
		src.includes('<TablePreview'),
		true,
		'WeatherMetricsTab.svelte muss <TablePreview ... /> im Template einbinden'
	);
});

// =============================================================================
// AC-2: SavePresetDialog — Custom Fixed-Overlay statt shadcn Dialog
// =============================================================================

test('AC-2a: SavePresetDialog importiert KEINEN shadcn Dialog mehr', () => {
	const src = readFrontend('lib/components/trip-detail/SavePresetDialog.svelte');
	assert.equal(
		src.includes("from '$lib/components/ui/dialog") ||
		src.includes('from "$lib/components/ui/dialog'),
		false,
		'SavePresetDialog.svelte darf keinen shadcn Dialog-Import mehr enthalten'
	);
});

test('AC-2b: SavePresetDialog verwendet KEIN Dialog.Root mehr', () => {
	const src = readFrontend('lib/components/trip-detail/SavePresetDialog.svelte');
	assert.equal(
		src.includes('Dialog.Root') || src.includes('<Dialog.Content'),
		false,
		'SavePresetDialog.svelte darf kein Dialog.Root / Dialog.Content mehr verwenden'
	);
});

test('AC-2c: SavePresetDialog hat Blur-Backdrop (backdrop-filter)', () => {
	const src = readFrontend('lib/components/trip-detail/SavePresetDialog.svelte');
	assert.equal(
		src.includes('backdrop-filter') || src.includes('backdropFilter'),
		true,
		'SavePresetDialog.svelte muss einen Blur-Backdrop via backdrop-filter enthalten'
	);
});

test('AC-2d: SavePresetDialog hat Eyebrow "EIGENES PRESET"', () => {
	const src = readFrontend('lib/components/trip-detail/SavePresetDialog.svelte');
	assert.equal(
		src.includes('EIGENES PRESET'),
		true,
		'SavePresetDialog.svelte muss Eyebrow mit Text "EIGENES PRESET" enthalten'
	);
});

test('AC-2e: SavePresetDialog Titel lautet "Auswahl als Preset speichern"', () => {
	const src = readFrontend('lib/components/trip-detail/SavePresetDialog.svelte');
	assert.equal(
		src.includes('Auswahl als Preset speichern'),
		true,
		'SavePresetDialog.svelte muss den Titel "Auswahl als Preset speichern" enthalten'
	);
});

test('AC-2f: Primär-Button im SavePresetDialog heißt "Preset speichern"', () => {
	const src = readFrontend('lib/components/trip-detail/SavePresetDialog.svelte');
	// "Preset speichern" als Button-Text (nicht nur "Speichern…" oder "Speichern")
	assert.equal(
		src.includes('Preset speichern'),
		true,
		'SavePresetDialog.svelte muss einen Button mit dem Text "Preset speichern" enthalten'
	);
});

test('AC-2g: SavePresetDialog hat position:fixed Overlay', () => {
	const src = readFrontend('lib/components/trip-detail/SavePresetDialog.svelte');
	assert.equal(
		src.includes('position: fixed') || src.includes('position:fixed'),
		true,
		'SavePresetDialog.svelte muss ein position:fixed Overlay-Element enthalten'
	);
});

// =============================================================================
// AC-3: ZEITHORIZONTE-Box bleibt erhalten (nach Overlay-Umbau)
// =============================================================================

test('AC-3a: SavePresetDialog hat data-testid="save-preset-horizon-summary"', () => {
	const src = readFrontend('lib/components/trip-detail/SavePresetDialog.svelte');
	assert.equal(
		src.includes('save-preset-horizon-summary'),
		true,
		'SavePresetDialog.svelte muss data-testid="save-preset-horizon-summary" enthalten'
	);
});

test('AC-3b: SavePresetDialog importiert computeHorizonSummary', () => {
	const src = readFrontend('lib/components/trip-detail/SavePresetDialog.svelte');
	assert.equal(
		src.includes('computeHorizonSummary'),
		true,
		'SavePresetDialog.svelte muss computeHorizonSummary importieren und verwenden'
	);
});

test('AC-3c: SavePresetDialog hat ZEITHORIZONTE-Eyebrow', () => {
	const src = readFrontend('lib/components/trip-detail/SavePresetDialog.svelte');
	assert.equal(
		src.includes('ZEITHORIZONTE'),
		true,
		'SavePresetDialog.svelte muss die ZEITHORIZONTE-Eyebrow enthalten'
	);
});
