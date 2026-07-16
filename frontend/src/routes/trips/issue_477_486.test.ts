// TDD RED: Issues #477 + #486 — Atomic-Design-Migration & Kebab-UX-Redesign
//
// Spec: docs/specs/modules/trips_atomic_kebab.md
// Route: /trips  →  frontend/src/routes/trips/+page.svelte
//
// Source-Inspection-Tests (analog zu issue_402.test.ts):
// Liest +page.svelte als String und prüft den Soll-Zustand nach Migration.
//
// RED-Erwartung:
//   AC-1 (5 Tests): FAIL — ui/table, ui/dialog, ui/checkbox, ui/select,
//     ui/empty-state sind noch in +page.svelte importiert
//   AC-4 (2 Tests): FAIL — 'Archivieren'/'Fertigstellen' existieren noch nicht
//   AC-5 (1 Test):  FAIL — 'Pausieren' fehlt im DropdownMenu
//   AC-6 (4 Tests): FAIL — ReportConfigDialog/TestReportDialog nicht vorhanden
//   Kebab-Label (1 Test): FAIL — 'Alerts justieren' noch als 'Report-Konfiguration'
//   Status-Caption (1 Test): FAIL — status-caption-Klasse noch nicht im Template
//
// HINWEIS: Nach Implementierung muss issue_402.test.ts AC-4 aktualisiert
//   werden, da es das Vorhandensein der ui/-Importe explizit prüft.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/routes/trips/issue_477_486.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const TRIPS_DIR = dirname(fileURLToPath(import.meta.url));
const PAGE_SVELTE = join(TRIPS_DIR, '+page.svelte');
const MOLECULES_DIR = join(TRIPS_DIR, '..', '..', 'lib', 'components', 'molecules');

function readPage(): string {
	return readFileSync(PAGE_SVELTE, 'utf-8');
}

// ── AC-1: Keine ui/-Importe mehr in +page.svelte ─────────────────────────────

describe('AC-1: Keine direkten ui/-Importe in +page.svelte', () => {
	test('AC-1a: kein ui/table-Import', () => {
		const src = readPage();
		assert.ok(
			!src.includes('ui/table'),
			"Import aus '$lib/components/ui/table' noch vorhanden — durch natives <table>-HTML ersetzen"
		);
	});

	test('AC-1b: kein ui/dialog-Import', () => {
		const src = readPage();
		assert.ok(
			!src.includes('ui/dialog'),
			"Import aus '$lib/components/ui/dialog' noch vorhanden — durch ConfirmDialog/ReportConfigDialog/TestReportDialog ersetzen"
		);
	});

	test('AC-1c: kein ui/checkbox-Import', () => {
		const src = readPage();
		assert.ok(
			!src.includes('ui/checkbox'),
			"Import aus '$lib/components/ui/checkbox' noch vorhanden — in ReportConfigDialog.svelte kapseln"
		);
	});

	test('AC-1d: kein ui/select-Import', () => {
		const src = readPage();
		assert.ok(
			!src.includes('ui/select'),
			"Import aus '$lib/components/ui/select' noch vorhanden — in ReportConfigDialog.svelte kapseln"
		);
	});

	test('AC-1e: kein ui/empty-state-Import', () => {
		const src = readPage();
		assert.ok(
			!src.includes('ui/empty-state'),
			"Import aus '$lib/components/ui/empty-state' noch vorhanden — inline mit Eyebrow + Btn ersetzen"
		);
	});
});

// ── AC-4: Primär-Button Status-Logik (HomeTripStatus) ────────────────────────

describe('AC-4: Primär-Button zeigt kontextsensitive Labels für alle Status', () => {
	test('AC-4a: Label "Archivieren" für fertige nicht-archivierte Trips vorhanden', () => {
		const src = readPage();
		// Prüft auf 'Archivieren' mit Großbuchstaben (≠ 'Dearchivieren' mit lowercase 'a')
		assert.match(
			src,
			/\bArchivieren\b/,
			'"Archivieren" fehlt in primaryLabel-Logik — für fertige, nicht archivierte Trips benötigt'
		);
	});

	test('AC-4b: Label "Fertigstellen" für draft-Trips vorhanden', () => {
		const src = readPage();
		assert.match(
			src,
			/Fertigstellen/,
			'"Fertigstellen" fehlt in primaryLabel-Logik — für draft-Trips benötigt (navigiert zu Wizard)'
		);
	});
});

// ── AC-5: Kebab-Menü enthält Pausieren/Reaktivieren ──────────────────────────

describe('AC-5: Kebab-Menü hat Pausieren/Reaktivieren-Eintrag', () => {
	test('AC-5: DropdownMenu enthält "Pausieren" als Menüeintrag', () => {
		const src = readPage();
		assert.match(
			src,
			/Pausieren/,
			'"Pausieren" fehlt im Kebab-Menü — nach "Bearbeiten" als DropdownMenu.Item einfügen'
		);
	});
});

// ── AC-6: Neue Molecules existieren und werden genutzt ───────────────────────

describe('AC-6: ReportConfigDialog und TestReportDialog Molecules', () => {
	test('AC-6a: ReportConfigDialog.svelte Datei existiert', () => {
		const path = join(MOLECULES_DIR, 'ReportConfigDialog.svelte');
		assert.ok(
			existsSync(path),
			'ReportConfigDialog.svelte existiert nicht — muss in molecules/ erstellt werden'
		);
	});

	test('AC-6b: TestReportDialog.svelte Datei existiert', () => {
		const path = join(MOLECULES_DIR, 'TestReportDialog.svelte');
		assert.ok(
			existsSync(path),
			'TestReportDialog.svelte existiert nicht — muss in molecules/ erstellt werden'
		);
	});

	test('AC-6c: +page.svelte importiert ReportConfigDialog', () => {
		const src = readPage();
		assert.match(
			src,
			/ReportConfigDialog/,
			'ReportConfigDialog wird in +page.svelte nicht genutzt — Import und Verwendung fehlen'
		);
	});

	test('AC-6d: +page.svelte importiert TestReportDialog', () => {
		const src = readPage();
		assert.match(
			src,
			/TestReportDialog/,
			'TestReportDialog wird in +page.svelte nicht genutzt — Import und Verwendung fehlen'
		);
	});
});

// ── Kebab-Label: "Alerts justieren" statt "Report-Konfiguration" ─────────────

describe('Kebab-Menü-Label aktualisiert', () => {
	test('Kebab enthält "Alerts justieren" statt "Report-Konfiguration"', () => {
		const src = readPage();
		assert.match(
			src,
			/Alerts justieren/,
			'"Alerts justieren" fehlt im Kebab-Menü — "Report-Konfiguration" muss umbenannt werden'
		);
	});
});

// ── Status-Caption: mono-Kürzel neben Trip-Name ──────────────────────────────
// Issue #1277: Die Desktop-Tabelle rendert die Namensspalte jetzt über das
// geteilte ListNameCell-Organism (organisms/ListNameCell.svelte) statt über
// Inline-Markup in +page.svelte. Der Status-Kürzel-Nachweis wandert daher
// mit auf die geteilte Komponente. Zusätzlich wird geprüft, dass die
// Trip-Übersicht dem Namens-Zelle einen Status-Label mitgibt.
describe('Status-Caption neben Trip-Name (geteilte ListNameCell)', () => {
	test('status-caption CSS-Klasse in ListNameCell vorhanden', () => {
		const nameCell = join(
			TRIPS_DIR,
			'..',
			'..',
			'lib',
			'components',
			'organisms',
			'ListNameCell.svelte'
		);
		const src = readFileSync(nameCell, 'utf-8');
		assert.match(
			src,
			/status-caption/,
			'"status-caption" CSS-Klasse fehlt in ListNameCell — Status-Kürzel neben Name einbauen'
		);
	});

	test('trips/+page.svelte übergibt der Namensspalte einen statusLabel', () => {
		const src = readPage();
		assert.match(
			src,
			/statusLabel/,
			'trips/+page.svelte muss der ListTable-Namensspalte einen statusLabel mitgeben (Status-Kürzel)'
		);
	});
});
