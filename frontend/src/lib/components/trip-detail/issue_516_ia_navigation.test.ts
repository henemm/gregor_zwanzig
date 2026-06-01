// TDD RED — Issue #516 + #506: Kanonische Navigations-Architektur + Etappen-Editor inline
//
// Spec: docs/specs/modules/issue_516_ia_navigation.md
//
// Source-Inspection-Tests: prüfen, dass die NEUEN Muster im Code vorhanden
// und die ALTEN Muster entfernt sind. Vor der Implementierung SCHEITERN sie (RED).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/issue_516_ia_navigation.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const ROOT = fileURLToPath(new URL('../../../..', import.meta.url)); // -> frontend/src root -> frontend root

function readFrontend(relPath: string): string {
	return readFileSync(join(ROOT, 'src', relPath), 'utf-8');
}

function readProject(relPath: string): string {
	// Go up from frontend/ to project root
	const projectRoot = join(ROOT, '..');
	return readFileSync(join(projectRoot, relPath), 'utf-8');
}

// ---------------------------------------------------------------------------
// AC-1: TripTabs.svelte — Tab-2-Label + Inline-Editor statt Redirect
// ---------------------------------------------------------------------------

test('AC-1a: TripTabs enthält "Etappen & Wegpunkte" als Tab-Label-String (nicht nur Kommentar)', () => {
	const src = readFrontend('lib/components/trip-detail/TripTabs.svelte');
	// Prüft den echten String-Wert im TABS-Array, nicht nur einen Kommentar
	assert.equal(
		src.includes("label: 'Etappen & Wegpunkte'") || src.includes('label: "Etappen & Wegpunkte"'),
		true,
		'TripTabs.svelte muss "Etappen & Wegpunkte" als label-Wert im TABS-Array enthalten (nicht nur im Kommentar)'
	);
});

test('AC-1b: TripTabs enthält EditStagesPanelNew Import', () => {
	const src = readFrontend('lib/components/trip-detail/TripTabs.svelte');
	assert.equal(
		src.includes('EditStagesPanelNew'),
		true,
		'TripTabs.svelte muss EditStagesPanelNew importieren und verwenden'
	);
});

test('AC-1c: TripTabs stages-Block enthält KEINEN Redirect-Link zu /edit', () => {
	const src = readFrontend('lib/components/trip-detail/TripTabs.svelte');
	assert.equal(
		src.includes('stages-redirect'),
		false,
		'TripTabs.svelte darf keinen stages-redirect-Block mehr enthalten (kein Link zu /edit)'
	);
});

// ---------------------------------------------------------------------------
// AC-2: EditStagesPanelNew.svelte — eigener Save-Button nach AlertsTab-Pattern
// ---------------------------------------------------------------------------

test('AC-2a: EditStagesPanelNew enthält api.put für Save', () => {
	const src = readFrontend('lib/components/edit/EditStagesPanelNew.svelte');
	assert.equal(
		src.includes('api.put'),
		true,
		'EditStagesPanelNew.svelte muss api.put für den Stage-Save enthalten'
	);
});

test('AC-2b: EditStagesPanelNew verwendet stripSuggested beim Speichern', () => {
	const src = readFrontend('lib/components/edit/EditStagesPanelNew.svelte');
	assert.equal(
		src.includes('stripSuggested'),
		true,
		'EditStagesPanelNew.svelte muss stripSuggested beim Save aufrufen'
	);
});

test('AC-2c: EditStagesPanelNew hat saveSuccess-State mit 3s-Flash', () => {
	const src = readFrontend('lib/components/edit/EditStagesPanelNew.svelte');
	assert.equal(
		src.includes('saveSuccess'),
		true,
		'EditStagesPanelNew.svelte muss saveSuccess-State für Erfolgs-Flash enthalten'
	);
	assert.equal(
		src.includes('3000'),
		true,
		'EditStagesPanelNew.svelte muss setTimeout mit 3000ms für den Flash enthalten'
	);
});

// ---------------------------------------------------------------------------
// AC-3: URL-Sync von #hash auf ?tab=
// ---------------------------------------------------------------------------

test('AC-3a: TripTabs nutzt goto mit replaceState statt history.replaceState/#hash', () => {
	const src = readFrontend('lib/components/trip-detail/TripTabs.svelte');
	assert.equal(
		src.includes('replaceState: true'),
		true,
		'TripTabs.svelte muss goto mit replaceState:true für URL-Sync verwenden'
	);
});

test('AC-3b: TripTabs enthält KEIN window.location.hash oder #-Hash-Schreiben', () => {
	const src = readFrontend('lib/components/trip-detail/TripTabs.svelte');
	assert.equal(
		src.includes('window.location.hash') || src.includes("'#'") || src.includes('`#${'),
		false,
		'TripTabs.svelte darf kein hash-basiertes URL-Update mehr enthalten'
	);
});

test('AC-3c: trips/[id]/+page.svelte liest initialTab aus searchParams', () => {
	const src = readFrontend('routes/trips/[id]/+page.svelte');
	assert.equal(
		src.includes("searchParams.get('tab')") || src.includes('searchParams.get("tab")'),
		true,
		'trips/[id]/+page.svelte muss initialTab aus page.url.searchParams.get("tab") lesen'
	);
});

test('AC-3d: trips/[id]/+page.svelte liest NICHT aus page.url.hash', () => {
	const src = readFrontend('routes/trips/[id]/+page.svelte');
	assert.equal(
		src.includes('page.url.hash') || src.includes('url.hash'),
		false,
		'trips/[id]/+page.svelte darf initialTab nicht mehr aus page.url.hash lesen'
	);
});

// ---------------------------------------------------------------------------
// AC-4: /trips/[id]/edit → HTTP-301-Redirect
// ---------------------------------------------------------------------------

test('AC-4a: edit/+page.server.ts enthält redirect(301', () => {
	const src = readFrontend('routes/trips/[id]/edit/+page.server.ts');
	assert.equal(
		src.includes('redirect(301'),
		true,
		'edit/+page.server.ts muss redirect(301 enthalten'
	);
});

test('AC-4b: edit/+page.server.ts redirectet auf ?tab=stages', () => {
	const src = readFrontend('routes/trips/[id]/edit/+page.server.ts');
	assert.equal(
		src.includes('?tab=stages'),
		true,
		'edit/+page.server.ts muss auf ?tab=stages redirecten'
	);
});

// ---------------------------------------------------------------------------
// AC-5: TripOverview — Etappen-Link auf ?tab=stages statt /edit
// ---------------------------------------------------------------------------

test('AC-5a: TripOverview enthält ?tab=stages für Etappen-Bearbeiten-Link', () => {
	const src = readFrontend('lib/components/trip-detail/TripOverview.svelte');
	assert.equal(
		src.includes('?tab=stages') || src.includes("tab=stages"),
		true,
		'TripOverview.svelte muss ?tab=stages für den Etappen-Bearbeiten-Link enthalten'
	);
});

test('AC-5b: TripOverview enthält KEINEN /edit-Link für Etappen mehr', () => {
	const src = readFrontend('lib/components/trip-detail/TripOverview.svelte');
	// Prüft: kein actionHref auf /edit (der Etappen-Bearbeiten-Link war /trips/{id}/edit)
	assert.equal(
		src.includes('/edit"') || src.includes("/edit'") || src.includes('`/edit`'),
		false,
		'TripOverview.svelte darf keinen /edit-Link mehr für Etappen-Bearbeiten enthalten'
	);
});

// ---------------------------------------------------------------------------
// AC-6: Hash-Migration — alle Preview/Alert/Briefing-Cards
// ---------------------------------------------------------------------------

test('AC-6a: AlertsPreviewCard enthält KEIN href="#alerts" mehr', () => {
	const src = readFrontend('lib/components/trip-detail/AlertsPreviewCard.svelte');
	assert.equal(
		src.includes('href="#alerts"'),
		false,
		'AlertsPreviewCard.svelte darf kein href="#alerts" mehr enthalten'
	);
});

test('AC-6b: AlertsPreviewCard enthält ?tab=alerts', () => {
	const src = readFrontend('lib/components/trip-detail/AlertsPreviewCard.svelte');
	assert.equal(
		src.includes('?tab=alerts') || src.includes('tab=alerts'),
		true,
		'AlertsPreviewCard.svelte muss ?tab=alerts enthalten'
	);
});

test('AC-6c: PreviewCard enthält KEIN href="#preview" mehr', () => {
	const src = readFrontend('lib/components/trip-detail/PreviewCard.svelte');
	assert.equal(
		src.includes('href="#preview"'),
		false,
		'PreviewCard.svelte darf kein href="#preview" mehr enthalten'
	);
});

test('AC-6d: BriefingPreviewCard enthält KEIN href="#briefings" mehr', () => {
	const src = readFrontend('lib/components/trip-detail/BriefingPreviewCard.svelte');
	assert.equal(
		src.includes('href="#briefings"'),
		false,
		'BriefingPreviewCard.svelte darf kein href="#briefings" mehr enthalten'
	);
});

test('AC-6e: WeatherMetricsPreviewCard enthält KEIN href="#weather" mehr', () => {
	const src = readFrontend('lib/components/trip-detail/WeatherMetricsPreviewCard.svelte');
	assert.equal(
		src.includes('href="#weather"'),
		false,
		'WeatherMetricsPreviewCard.svelte darf kein href="#weather" mehr enthalten'
	);
});

// ---------------------------------------------------------------------------
// AC-7: EditStagesPanelNew — showSave-Prop um Save-Button
// ---------------------------------------------------------------------------

test('AC-7: EditStagesPanelNew hat showSave-Guard um den Save-Button-Block', () => {
	const src = readFrontend('lib/components/edit/EditStagesPanelNew.svelte');
	assert.equal(
		src.includes('showSave'),
		true,
		'EditStagesPanelNew.svelte muss showSave-Prop als Guard für den Save-Button enthalten'
	);
});

// ---------------------------------------------------------------------------
// AC-8: TripTabs — Guard gegen undefined trip
// ---------------------------------------------------------------------------

test('AC-8: TripTabs hat {#if trip} Guard um EditStagesPanelNew-Einbindung', () => {
	const src = readFrontend('lib/components/trip-detail/TripTabs.svelte');
	// Prüft, dass EditStagesPanelNew nur gerendert wird wenn trip existiert
	assert.equal(
		src.includes('{#if trip}') || src.includes('if (trip)'),
		true,
		'TripTabs.svelte muss einen {#if trip} Guard um die EditStagesPanelNew-Einbindung haben'
	);
});
