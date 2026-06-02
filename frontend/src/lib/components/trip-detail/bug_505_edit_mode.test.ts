// TDD RED — Bug #505: "Bearbeiten"- und "Briefing-Vorschau"-Button aus Trip-Header entfernen
//
// Spec: docs/specs/modules/bug_505_speichern_bearbeiten.md
//
// Source-Inspection-Tests: prüfen, dass die ALTEN Muster (Buttons/Handler) entfernt sind
// und die Tab-Edit-Muster korrekt vorhanden sind.
// Vor der Implementierung SCHEITERN AC-1, AC-2, AC-3 (RED).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/bug_505_edit_mode.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const ROOT = fileURLToPath(new URL('../../../..', import.meta.url)); // -> frontend root

function readFrontend(relPath: string): string {
	return readFileSync(join(ROOT, 'src', relPath), 'utf-8');
}

// ---------------------------------------------------------------------------
// AC-1: TripHeader — kein "Bearbeiten"-Button mehr
// ---------------------------------------------------------------------------

test('AC-1: TripHeader enthält KEINEN Button mit data-testid="trip-detail-action-edit"', () => {
	const src = readFrontend('lib/components/trip-detail/TripHeader.svelte');
	assert.equal(
		src.includes('trip-detail-action-edit'),
		false,
		'TripHeader.svelte darf keinen Button mit data-testid="trip-detail-action-edit" mehr enthalten'
	);
});

// ---------------------------------------------------------------------------
// AC-2: TripHeader — kein "Briefing-Vorschau"-Button mehr
// ---------------------------------------------------------------------------

test('AC-2: TripHeader enthält KEINEN Button mit data-testid="trip-detail-action-preview"', () => {
	const src = readFrontend('lib/components/trip-detail/TripHeader.svelte');
	assert.equal(
		src.includes('trip-detail-action-preview'),
		false,
		'TripHeader.svelte darf keinen Button mit data-testid="trip-detail-action-preview" mehr enthalten'
	);
});

// ---------------------------------------------------------------------------
// AC-3: TripHeader — keine handleEdit / handlePreview Handler mehr
// ---------------------------------------------------------------------------

test('AC-3a: TripHeader enthält KEINEN handleEdit-Handler', () => {
	const src = readFrontend('lib/components/trip-detail/TripHeader.svelte');
	assert.equal(
		src.includes('handleEdit'),
		false,
		'TripHeader.svelte darf keine handleEdit-Funktion mehr enthalten'
	);
});

test('AC-3b: TripHeader enthält KEINEN handlePreview-Handler', () => {
	const src = readFrontend('lib/components/trip-detail/TripHeader.svelte');
	assert.equal(
		src.includes('handlePreview'),
		false,
		'TripHeader.svelte darf keine handlePreview-Funktion mehr enthalten'
	);
});

// ---------------------------------------------------------------------------
// AC-4: Etappen-Tab — EditStagesPanelNew mit showSave={true} + api.put
// ---------------------------------------------------------------------------

test('AC-4a: TripTabs bindet EditStagesPanelNew mit showSave={true} ein', () => {
	const src = readFrontend('lib/components/trip-detail/TripTabs.svelte');
	assert.equal(
		src.includes('showSave={true}'),
		true,
		'TripTabs.svelte muss EditStagesPanelNew mit showSave={true} einbinden'
	);
});

test('AC-4b: EditStagesPanelNew enthält api.put für den Save-Call', () => {
	const src = readFrontend('lib/components/edit/EditStagesPanelNew.svelte');
	assert.equal(
		src.includes('api.put'),
		true,
		'EditStagesPanelNew.svelte muss api.put für den Etappen-Save enthalten'
	);
});

// ---------------------------------------------------------------------------
// AC-5: Wetter-Tab — WeatherMetricsTab hat Speichern-Button
// ---------------------------------------------------------------------------

test('AC-5: WeatherMetricsTab enthält Button mit data-testid="weather-metrics-tab-save"', () => {
	const src = readFrontend('lib/components/trip-detail/WeatherMetricsTab.svelte');
	assert.equal(
		src.includes('weather-metrics-tab-save'),
		true,
		'WeatherMetricsTab.svelte muss einen Button mit data-testid="weather-metrics-tab-save" enthalten'
	);
});

// ---------------------------------------------------------------------------
// AC-6: Briefings-Tab — BriefingsTab hat Speichern-Button
// ---------------------------------------------------------------------------

test('AC-6: BriefingsTab enthält Button mit data-testid="briefings-tab-save"', () => {
	const src = readFrontend('lib/components/briefings-tab/BriefingsTab.svelte');
	assert.equal(
		src.includes('briefings-tab-save'),
		true,
		'BriefingsTab.svelte muss einen Button mit data-testid="briefings-tab-save" enthalten'
	);
});

// ---------------------------------------------------------------------------
// AC-7: Alerts-Tab — AlertsTab hat Speichern-Button
// ---------------------------------------------------------------------------

test('AC-7: AlertsTab enthält Button mit data-testid="alerts-tab-save"', () => {
	const src = readFrontend('lib/components/alerts-tab/AlertsTab.svelte');
	assert.equal(
		src.includes('alerts-tab-save'),
		true,
		'AlertsTab.svelte muss einen Button mit data-testid="alerts-tab-save" enthalten'
	);
});
