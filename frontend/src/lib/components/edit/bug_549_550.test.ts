// Bug #549 + #550 — TDD RED Source-Inspection-Tests
//
// SPEC: docs/specs/modules/bug_545_549_550_retrospective_fixes.md
// AC-3: stages-Tab in TripTabs.svelte enthält KEIN editierbares Formular (EditStagesPanelNew)
// AC-4: stages-Tab enthält Redirect-Link zu /trips/{id}/edit
// AC-5: EditStagesSection.svelte + EditWeatherSection.svelte existieren in edit/
//
// Methodik: node:test + readFileSync/existsSync — Source-Inspection ohne DOM-Rendering.
// Keine Mocks (CLAUDE.md: Mocks verboten).
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/edit/bug_549_550.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));

const TRIP_TABS = join(here, '..', 'trip-detail', 'TripTabs.svelte');
const EDIT_STAGES_SECTION = join(here, 'EditStagesSection.svelte');
const EDIT_WEATHER_SECTION = join(here, 'EditWeatherSection.svelte');

// ────────────────────────────────────────────────────────────────────────────
// Bug #549 — TripTabs.svelte: stages-Tab darf kein inline-EditStagesPanelNew rendern
// ────────────────────────────────────────────────────────────────────────────

describe('Bug #549 TripTabs stages-Tab — Leseansicht, kein inline-Editor', () => {
	test('AC-3: stages-Tab enthält kein <EditStagesPanelNew', () => {
		const src = readFileSync(TRIP_TABS, 'utf-8');
		assert.ok(
			!src.includes('<EditStagesPanelNew'),
			'TripTabs.svelte darf EditStagesPanelNew NICHT rendern — ' +
				'stages-Tab ist Leseansicht (Spec issue-503 AC-2, bug_545_549_550 AC-3)'
		);
	});

	test('AC-4: stages-Tab enthält href-Link zu /trips/.../edit', () => {
		const src = readFileSync(TRIP_TABS, 'utf-8');
		// Nach Fix: <a href="/trips/{trip.id}/edit"> oder href={`/trips/${trip.id}/edit`}
		// Prüft auf href-Attribut mit /trips/ + /edit — nicht nur Import-Pfad
		const hasEditHref =
			src.includes('href="/trips/') ||
			src.includes("href='/trips/") ||
			src.includes('href={`/trips/') ||
			src.includes('href=\'/trips/');
		assert.ok(
			hasEditHref,
			'stages-Tab muss einen href-Link zu /trips/{id}/edit enthalten (bug_545_549_550 AC-4)'
		);
	});
});

// ────────────────────────────────────────────────────────────────────────────
// Bug #550 — EditStagesSection + EditWeatherSection müssen existieren
// ────────────────────────────────────────────────────────────────────────────

describe('Bug #550 Edit*Section Komponenten vorhanden', () => {
	test('AC-5a: EditStagesSection.svelte existiert', () => {
		assert.ok(
			existsSync(EDIT_STAGES_SECTION),
			'EditStagesSection.svelte fehlt in frontend/src/lib/components/edit/ ' +
				'(Spec issue_190_alter_wizard_cleanup.md AC-2)'
		);
	});

	test('AC-5b: EditWeatherSection.svelte existiert', () => {
		assert.ok(
			existsSync(EDIT_WEATHER_SECTION),
			'EditWeatherSection.svelte fehlt in frontend/src/lib/components/edit/ ' +
				'(Spec issue_190_alter_wizard_cleanup.md AC-2)'
		);
	});
});
