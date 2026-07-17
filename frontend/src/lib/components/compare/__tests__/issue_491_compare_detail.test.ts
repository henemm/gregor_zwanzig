// TDD RED — Issue #491: /compare/[id] Detailseite (Block C, Epic #485)
//
// Spec: docs/specs/modules/issue_491_compare_detail.md
//
// Source-Inspection-Tests: prüfen Soll-Zustand nach Implementation.
//
// RED-Erwartung (vor Implementation):
//   AC-1: FAIL — /compare/[id]/+page.svelte existiert nicht
//   AC-2: FAIL — /compare/[id]/+page.server.ts existiert nicht
//   AC-3: FAIL — +page.svelte importiert CompareStatusPill, CompareKebab, CompareLocationRow nicht
//   AC-4: FAIL — +page.svelte importiert NICHT CompareIdealRow / CompareLayoutRow (out-of-scope)
//   AC-5: FAIL — +page.server.ts nutzt /api/compare/presets (nicht einzelnen Endpoint)
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_491_compare_detail.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const COMPARE_DIR = dirname(fileURLToPath(import.meta.url)) + '/..';
const ROUTES_COMPARE_ID = join(
	COMPARE_DIR,
	'..', '..', '..', 'routes', 'compare', '[id]'
);

const PAGE_SVELTE   = join(ROUTES_COMPARE_ID, '+page.svelte');
const PAGE_SERVER   = join(ROUTES_COMPARE_ID, '+page.server.ts');

// ── Datei-Existenz ────────────────────────────────────────────────────────────

describe('AC-Exist: Neue Dateien erstellt', () => {
	test('/compare/[id]/+page.svelte existiert', () => {
		assert.ok(
			existsSync(PAGE_SVELTE),
			'/compare/[id]/+page.svelte fehlt — neue Route muss erstellt werden'
		);
	});

	test('/compare/[id]/+page.server.ts existiert', () => {
		assert.ok(
			existsSync(PAGE_SERVER),
			'/compare/[id]/+page.server.ts fehlt — Server-Loader muss erstellt werden'
		);
	});
});

// ── AC-1: Preset-Daten werden angezeigt ──────────────────────────────────────

describe('AC-1: Preset-Name, Status, Schedule, Empfänger angezeigt', () => {
	test('+page.svelte importiert CompareStatusPill', () => {
		assert.ok(existsSync(PAGE_SVELTE), '+page.svelte fehlt');
		const src = readFileSync(PAGE_SVELTE, 'utf-8');
		assert.match(
			src,
			/CompareStatusPill/,
			'CompareStatusPill wird in +page.svelte nicht importiert oder verwendet'
		);
	});

	test('+page.svelte importiert CompareKebab für Aktionsmenü', () => {
		assert.ok(existsSync(PAGE_SVELTE), '+page.svelte fehlt');
		const src = readFileSync(PAGE_SVELTE, 'utf-8');
		assert.match(
			src,
			/CompareKebab/,
			'CompareKebab wird in +page.svelte nicht importiert — Aktionsmenü fehlt'
		);
	});

	test('+page.svelte zeigt Preset-Name an', () => {
		assert.ok(existsSync(PAGE_SVELTE), '+page.svelte fehlt');
		const src = readFileSync(PAGE_SVELTE, 'utf-8');
		// Epic #1273 S2: Anzeige liest jetzt aus dem reaktiven `currentPreset`-
		// Spiegel statt direkt aus `data.preset` (Adversary-Fund: `data` aus
		// $props() ist nicht tief-reaktiv fuer Nested-Mutation) — Pattern
		// deckt beide Varianten ab.
		assert.match(
			src,
			/(?:current)?[Pp]reset\.name/,
			'+page.svelte zeigt preset.name nicht an'
		);
	});
});

// ── AC-2: Standort-Kacheln via CompareLocationRow ────────────────────────────
// Issue #1256 Scheibe 8 (AC-22, Ein-Mount-Strategie): die nummerierte
// Standort-Liste lebt nicht mehr bespoke in +page.svelte, sondern im geteilten
// Orte-Tab von CompareTabs.svelte (über CompareDetail gemountet) — dort für
// Desktop UND Mobile gemeinsam.

describe('AC-2: Nummerierte Standort-Kacheln vorhanden (geteilter Orte-Tab)', () => {
	const TABS = join(COMPARE_DIR, 'CompareTabs.svelte');

	test('CompareTabs.svelte importiert CompareLocationRow', () => {
		assert.ok(existsSync(TABS), 'CompareTabs.svelte fehlt');
		const src = readFileSync(TABS, 'utf-8');
		assert.match(
			src,
			/CompareLocationRow/,
			'CompareLocationRow wird in CompareTabs.svelte nicht importiert — Standortliste fehlt'
		);
	});

	// Issue #1272: die Orte-Schleife lebt nicht mehr bespoke hier, sondern im
	// geteilten Sortier-Baustein `shared/dnd/SortableList` (ADR-0024).
	// CompareTabs liefert ihm die Liste und rendert die Zeile per Snippet.
	test('CompareTabs.svelte rendert die Orte-Liste über den geteilten SortableList', () => {
		assert.ok(existsSync(TABS), 'CompareTabs.svelte fehlt');
		const src = readFileSync(TABS, 'utf-8');
		assert.match(
			src,
			/<SortableList[\s\S]*?items=\{currentLocationIds\}/,
			'CompareTabs.svelte speist die Orte-Liste nicht in den geteilten SortableList'
		);
		assert.match(
			src,
			/data-testid="hub-orte-row"/,
			'CompareTabs.svelte rendert keine hub-orte-row für die Standortliste'
		);
	});
});

// ── AC-3: 404 bei ungültiger ID ───────────────────────────────────────────────

describe('AC-3: Server-Loader wirft 404 bei unbekannter ID', () => {
	test('+page.server.ts importiert error() von @sveltejs/kit', () => {
		assert.ok(existsSync(PAGE_SERVER), '+page.server.ts fehlt');
		const src = readFileSync(PAGE_SERVER, 'utf-8');
		assert.match(
			src,
			/error.*@sveltejs\/kit|from '@sveltejs\/kit'.*error/,
			"error() aus '@sveltejs/kit' wird nicht importiert — 404 nicht möglich"
		);
	});

	test('+page.server.ts nutzt /api/compare/presets-Endpoint (list oder single)', () => {
		assert.ok(existsSync(PAGE_SERVER), '+page.server.ts fehlt');
		const src = readFileSync(PAGE_SERVER, 'utf-8');
		assert.match(
			src,
			/api\/compare\/presets/,
			'+page.server.ts ruft /api/compare/presets nicht auf'
		);
	});
});

// ── AC-4: Out-of-Scope: kein CompareIdealRow / CompareLayoutRow ───────────────

describe('AC-4 Out-of-Scope-Guard: CompareIdealRow und CompareLayoutRow NICHT importiert', () => {
	test('+page.svelte importiert NICHT CompareIdealRow (kein display_config im Typ)', () => {
		if (!existsSync(PAGE_SVELTE)) return; // Skip wenn Datei noch nicht erstellt
		const src = readFileSync(PAGE_SVELTE, 'utf-8');
		assert.ok(
			!src.includes('CompareIdealRow'),
			'CompareIdealRow ist in +page.svelte importiert — out of scope, ComparePreset hat kein display_config'
		);
	});

	test('+page.svelte importiert NICHT CompareLayoutRow (kein display_config im Typ)', () => {
		if (!existsSync(PAGE_SVELTE)) return; // Skip wenn Datei noch nicht erstellt
		const src = readFileSync(PAGE_SVELTE, 'utf-8');
		assert.ok(
			!src.includes('CompareLayoutRow'),
			'CompareLayoutRow ist in +page.svelte importiert — out of scope, ComparePreset hat kein display_config'
		);
	});
});

// ── AC-5: Build-Sicherheit ────────────────────────────────────────────────────

describe('AC-5: Server-Loader lädt auch /api/locations für Standort-Namen', () => {
	test('+page.server.ts ruft /api/locations ab', () => {
		assert.ok(existsSync(PAGE_SERVER), '+page.server.ts fehlt');
		const src = readFileSync(PAGE_SERVER, 'utf-8');
		assert.match(
			src,
			/api\/locations/,
			'+page.server.ts ruft /api/locations nicht ab — Standort-Namen können nicht aufgelöst werden'
		);
	});

	test('+page.server.ts filtert Locations nach location_ids', () => {
		assert.ok(existsSync(PAGE_SERVER), '+page.server.ts fehlt');
		const src = readFileSync(PAGE_SERVER, 'utf-8');
		assert.match(
			src,
			/location_ids|filter.*locations|locations.*filter/,
			'+page.server.ts filtert locations nicht nach preset.location_ids'
		);
	});
});
