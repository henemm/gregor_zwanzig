// TDD RED: Issue #580 — Design-Fidelity: Trips-Liste 1:1 nach screen-trips.jsx
//
// Spec: docs/specs/modules/issue_580_trips_liste.md
// Route: /trips  →  frontend/src/routes/trips/+page.svelte
//
// Source-Inspection-Tests: Liest +page.svelte als String und prüft den
// SOLL-Zustand nach der Design-Fidelity-Migration.
//
// RED-Erwartung (IST-Stand schlägt fehl weil):
//   AC-1 (2 Tests): FAIL — Stat-Atom mit layout="inline" / tone="accent" fehlt
//   AC-2 (2 Tests): FAIL — CSS-Grid "1.6fr 0.8fr 1.4fr auto" fehlt, var(--g-paper-deep) fehlt
//   AC-3 (3 Tests): FAIL — 6 ActionBtns (alert/weather/play/preview/edit/trash) fehlen
//   AC-4 (2 Tests): FAIL — width:30px / border: var(--g-rule-soft) / border-radius: var(--g-r-2) fehlen
//   AC-5 (2 Tests): FAIL — H1-Titel "Trips" und Footer "von … Trips" fehlen
//   AC-6 (2 Tests): PASS  — Mobile Card-Stack ist unverändert vorhanden
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/routes/trips/issue_580.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const TRIPS_DIR = dirname(fileURLToPath(import.meta.url));
const PAGE_SVELTE = join(TRIPS_DIR, '+page.svelte');

function readPage(): string {
	return readFileSync(PAGE_SVELTE, 'utf-8');
}

// ── AC-1: Stats-Bar nutzt Stat-Atom mit layout="inline" und tone="accent" ────

describe('AC-1: Stats-Bar — Stat-Atom mit layout="inline"', () => {
	test('AC-1a: Stat-Atom ist importiert', () => {
		const src = readPage();
		assert.ok(
			src.includes('Stat') && src.includes('atoms'),
			'Stat-Atom aus $lib/components/atoms nicht importiert — Stats-Bar muss Stat-Atoms nutzen'
		);
	});

	test('AC-1b: layout="inline" und tone="accent" vorhanden', () => {
		const src = readPage();
		assert.ok(
			src.includes('layout="inline"') && src.includes('tone="accent"'),
			'layout="inline" oder tone="accent" fehlen — Stat-Atom für SummaryStat-Bar benötigt diese Props'
		);
	});
});

// ── AC-2: Desktop-Tabelle nutzt CSS-Grid "1.6fr 0.8fr 1.4fr auto" ────────────

describe('AC-2: Desktop Grid-Tabelle', () => {
	test('AC-2a: gridTemplateColumns "1.6fr 0.8fr 1.4fr auto" vorhanden', () => {
		const src = readPage();
		assert.ok(
			src.includes('1.6fr') && src.includes('0.8fr') && src.includes('1.4fr'),
			'CSS-Grid-Spalten "1.6fr 0.8fr 1.4fr auto" fehlen — Desktop-Table muss Grid-Layout nutzen statt <table>'
		);
	});

	test('AC-2b: Header-Zeile mit var(--g-paper-deep) Hintergrund', () => {
		const src = readPage();
		assert.ok(
			src.includes('g-paper-deep'),
			'var(--g-paper-deep) fehlt — Grid-Header-Zeile benötigt diesen Hintergrund-Token'
		);
	});
});

// ── AC-3: TripRow zeigt Dot + Name + 6 ActionBtns ────────────────────────────

describe('AC-3: TripRow — Dot + Name + 6 ActionBtns', () => {
	test('AC-3a: Dot-Komponente mit farbigem Status-Punkt vorhanden', () => {
		const src = readPage();
		// Dot aus atoms oder ein 7px-borderRadius-Span mit Statusfarbe
		assert.ok(
			src.includes('border-radius: 50%') || (src.includes('<Dot') && src.includes('g-accent')),
			'Kein 7px-Statuspunkt gefunden — TripRow braucht farbigen Dot (7px, border-radius:50%)'
		);
	});

	test('AC-3b: 6 ActionBtn-Typen (alert/weather/play/preview/edit/trash) vorhanden', () => {
		const src = readPage();
		const hasAlert   = src.includes('alert');
		const hasWeather = src.includes('weather');
		const hasPlay    = src.includes('play') || src.includes('Play');
		const hasPreview = src.includes('preview');
		const hasEdit    = src.includes('edit') || src.includes('Edit');
		const hasTrash   = src.includes('trash') || src.includes('Trash');
		assert.ok(
			hasAlert && hasWeather && hasPlay && hasPreview && hasEdit && hasTrash,
			'Nicht alle 6 ActionBtn-Typen gefunden (alert/weather/play/preview/edit/trash) — Einzelbuttons statt DropdownMenu benötigt'
		);
	});

	test('AC-3c: Kein DropdownMenu mehr im Desktop-Block', () => {
		const src = readPage();
		// DropdownMenu darf nur noch im Mobile-Block existieren, nicht im Desktop-Grid
		// Prüfen: wenn grid-template vorhanden, darf DropdownMenu.Root nicht im gleichen Block sein
		// Vereinfacht: Desktop-Section hat kein DropdownMenu.Root mehr
		assert.ok(
			!src.includes('DropdownMenu.Root'),
			'DropdownMenu.Root noch in der Seite — Desktop-Block muss 6 Einzelbuttons nutzen statt Dropdown'
		);
	});
});

// ── AC-4: ActionBtn — 30px × 30px, border, border-radius ─────────────────────

describe('AC-4: ActionBtn — Dimensionen und Styles', () => {
	test('AC-4a: ActionBtn-Breite/Höhe 30px vorhanden', () => {
		const src = readPage();
		assert.ok(
			src.includes('30px') || src.includes('width: 30') || src.includes('w-[30px]'),
			'30px-Dimension für ActionBtns fehlt — Buttons müssen 30×30px sein'
		);
	});

	test('AC-4b: border: 1px solid var(--g-rule-soft) vorhanden', () => {
		const src = readPage();
		assert.ok(
			src.includes('g-rule-soft'),
			'var(--g-rule-soft) fehlt — ActionBtns benötigen border: 1px solid var(--g-rule-soft)'
		);
	});
});

// ── AC-5: H1-Titel "Trips" und Footer "{N} von {M} Trips" ────────────────────

describe('AC-5: Titel und Footer', () => {
	test('AC-5a: H1-Titel lautet "Trips" (nicht "Meine Trips")', () => {
		const src = readPage();
		assert.ok(
			!src.includes('Meine Trips'),
			'H1-Titel lautet noch "Meine Trips" — muss auf "Trips" geändert werden'
		);
	});

	test('AC-5b: Footer zeigt "{N} von {M} Trips"', () => {
		const src = readPage();
		assert.ok(
			src.includes('von') && src.includes('Trips') && (src.includes('.length') || src.includes('length}')),
			'Footer mit "{N} von {M} Trips"-Pattern fehlt — Fußzeile braucht Mono-11px-Zähler'
		);
	});
});

// ── AC-6: Mobile Card-Stack und Filter-Pills unverändert ──────────────────────

describe('AC-6: Mobile-Schutz — Card-Stack und Filter-Pills unverändert', () => {
	test('AC-6a: Mobile Card-Stack (data-testid="trip-card-stack") noch vorhanden', () => {
		const src = readPage();
		assert.ok(
			src.includes('trip-card-stack'),
			'Mobile Card-Stack (data-testid="trip-card-stack") fehlt — Mobile-Ansicht darf nicht verändert werden'
		);
	});

	test('AC-6b: Mobile Filter-Pills noch vorhanden', () => {
		const src = readPage();
		assert.ok(
			src.includes('mobileFilter') || src.includes('mobile-filter') || src.includes('Filter'),
			'Mobile Filter-Pills fehlen — Mobile-Ansicht darf nicht verändert werden'
		);
	});
});
