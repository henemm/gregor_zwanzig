// TDD RED: Issue #390 — Compare-Screen auf Atomic-Bibliothek migrieren
//
// Spec:  docs/specs/modules/issue_390_compare_atomic_migration.md
//
// Source-Inspection-Tests (wie contrast-audit.test.ts): lesen echte .svelte-Dateien
// und pruefen, dass die Migration vollstaendig durchgefuehrt wurde.
//
// RED-Erwartung (vor Implementation):
//   - +page.svelte hat kein Pill-Import und noch alte rounded-full-Klassen → FAIL
//   - PresetHeader.svelte hat kein Field-Import und noch alte label-Markup → FAIL
//   - GroupSection.svelte hat kein data-slot="dot" fuer Locations → FAIL
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_390_atomic_migration.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const ROOT = fileURLToPath(new URL('../../../../../', import.meta.url)); // -> frontend/

const PAGE = join(ROOT, 'src/routes/compare/+page.svelte');
const PRESET_HEADER = join(ROOT, 'src/lib/components/compare/PresetHeader.svelte');
const GROUP_SECTION = join(ROOT, 'src/lib/components/compare/GroupSection.svelte');

// ── AC-1 + AC-5: +page.svelte — ChipBtn → Pill ────────────────────────────
//
// OBSOLET durch Issue #439: routes/compare/+page.svelte ist nicht mehr der
// interaktive Vergleichsrechner, sondern eine Tabellen-Übersicht aller Orts-
// Vergleiche. Es gibt keine Mobile-Chip-Row mehr und keinen direkten Pill-
// Import; die alten interaktiven Composites (LocationsRail, PresetHeader,
// CompareMatrix etc.) leben weiter, aber gehören nicht mehr in /compare.
// Die folgenden Tests werden als historische Dokumentation belassen und mit
// test.skip markiert — die zugrundeliegenden Composites bleiben unverändert.

test.skip('AC-1: +page.svelte importiert Pill aus atoms (obsolet durch #439)', () => {
	const src = readFileSync(PAGE, 'utf-8');
	assert.match(
		src,
		/import\s*\{[^}]*\bPill\b[^}]*\}\s*from\s*['"][^'"]*ui\/pill[^'"]*['"]/,
		'+page.svelte muss Pill aus $lib/components/ui/pill importieren'
	);
});

test.skip('AC-1: Mobile Chip-Row nutzt <Pill> statt inline-Button-Klassen (obsolet durch #439)', () => {
	const src = readFileSync(PAGE, 'utf-8');
	const chipRowBlock = src.match(
		/data-testid="compare-mobile-chip-row"[\s\S]*?(?=<\/div>\s*<Btn|<Btn\s+data-testid="compare-mobile-open-sheet")/
	)?.[0] ?? '';
	assert.ok(chipRowBlock.length > 0, 'compare-mobile-chip-row Block nicht gefunden');
	assert.match(chipRowBlock, /<Pill/, 'Chip-Row muss <Pill>-Element enthalten');
});

test('AC-5: Alte inline-Button-Klassen aus Mobile Chip-Row entfernt', () => {
	const src = readFileSync(PAGE, 'utf-8');
	// "rounded-full border border-border bg-muted" darf in der Chip-Row nicht mehr vorkommen
	// Wir pruefen im gesamten File, da diese Kombination nur in der Chip-Row vorkam
	assert.doesNotMatch(
		src,
		/rounded-full border border-border bg-muted/,
		'Alte inline Chip-Button-Klassen (rounded-full border border-border bg-muted) muessen entfernt sein'
	);
});

test.skip('AC-1: Mobile Chip-Buttons haben aria-pressed (obsolet durch #439)', () => {
	const src = readFileSync(PAGE, 'utf-8');
	const chipRowBlock = src.match(
		/data-testid="compare-mobile-chip-row"[\s\S]*?(?=<Btn\s+data-testid="compare-mobile-open-sheet")/
	)?.[0] ?? '';
	assert.ok(chipRowBlock.length > 0, 'compare-mobile-chip-row Block nicht gefunden');
	assert.match(chipRowBlock, /aria-pressed/, 'Chip-Buttons muessen aria-pressed haben');
});

// ── AC-2 + AC-5: PresetHeader.svelte — CompareField → Field ───────────────

test('AC-2: PresetHeader.svelte importiert Field aus molecules', () => {
	const src = readFileSync(PRESET_HEADER, 'utf-8');
	assert.match(
		src,
		/import\s*\{[^}]*\bField\b[^}]*\}\s*from\s*['"][^'"]*molecules[^'"]*['"]/,
		'PresetHeader.svelte muss Field aus $lib/components/molecules importieren'
	);
});

test('AC-2: PresetHeader.svelte nutzt <Field>-Wrapper', () => {
	const src = readFileSync(PRESET_HEADER, 'utf-8');
	const fieldMatches = [...src.matchAll(/<Field\b/g)];
	assert.ok(
		fieldMatches.length >= 5,
		`PresetHeader muss mindestens 5 <Field>-Elemente enthalten, gefunden: ${fieldMatches.length}`
	);
});

test('AC-5: Alte label-Klasse "text-sm font-medium" aus PresetHeader entfernt', () => {
	const src = readFileSync(PRESET_HEADER, 'utf-8');
	// Die alten <label class="text-sm font-medium">-Tags duerften weg sein
	assert.doesNotMatch(
		src,
		/<label[^>]*class="text-sm font-medium"/,
		'Alte <label class="text-sm font-medium"> muessen entfernt sein (ersetzt durch Field)'
	);
});

test('AC-2: data-testid="compare-preset-date-input" bleibt erhalten', () => {
	const src = readFileSync(PRESET_HEADER, 'utf-8');
	assert.match(
		src,
		/data-testid="compare-preset-date-input"/,
		'data-testid="compare-preset-date-input" muss im PresetHeader erhalten bleiben'
	);
});

test('AC-2: data-testid="compare-preset-profile-select" bleibt erhalten', () => {
	const src = readFileSync(PRESET_HEADER, 'utf-8');
	assert.match(
		src,
		/data-testid="compare-preset-profile-select"/,
		'data-testid="compare-preset-profile-select" muss im PresetHeader erhalten bleiben'
	);
});

// ── AC-3: GroupSection.svelte — FocusBadge → data-slot="dot" ─────────────

test('AC-3: GroupSection.svelte rendert data-slot="dot" INNERHALB des {#each locations}-Blocks', () => {
	const src = readFileSync(GROUP_SECTION, 'utf-8');
	// Pruefen dass data-slot="dot" in Kombination mit loc.activity_profile vorkommt
	// (nicht nur der Gruppen-Header-Dot der group.default_profile nutzt)
	assert.match(
		src,
		/loc\.activity_profile[\s\S]{0,300}data-slot="dot"|data-slot="dot"[\s\S]{0,300}loc\.activity_profile/,
		'GroupSection muss data-slot="dot" im {#each locations}-Block (mit loc.activity_profile) enthalten'
	);
});

test('AC-3: GroupSection Profil-Dot nutzt profileSignature(...).accent als background', () => {
	const src = readFileSync(GROUP_SECTION, 'utf-8');
	assert.match(
		src,
		/profileSignature\([^)]*\)\.accent/,
		'GroupSection Profil-Dot muss profileSignature(...).accent als Hintergrundfarbe nutzen'
	);
});

test('AC-3: GroupSection Profil-Dot hat title-Attribut mit eyebrow-Label', () => {
	const src = readFileSync(GROUP_SECTION, 'utf-8');
	assert.match(
		src,
		/profileSignature\([^)]*\)\.eyebrow/,
		'GroupSection Profil-Dot muss profileSignature(...).eyebrow als title haben'
	);
});

// ── AC-6: Page-lokale Komposita unveraendert ───────────────────────────────

const PAGE_LOCAL_COMPOSITES = [
	'src/lib/components/compare/CompareMatrix.svelte',
	'src/lib/components/compare/HourlyMatrix.svelte',
	'src/lib/components/compare/RecommendationBanner.svelte',
	'src/lib/components/compare/AutoReportsOverview.svelte',
];

for (const relPath of PAGE_LOCAL_COMPOSITES) {
	test(`AC-6: ${relPath} existiert (Composite bleibt unveraendert)`, () => {
		const fullPath = join(ROOT, relPath);
		// Testet nur Existenz — Git-diff wird manuell geprueft
		const src = readFileSync(fullPath, 'utf-8');
		assert.ok(src.length > 100, `${relPath} muss eine echte Komponente sein (>100 Zeichen)`);
	});
}
