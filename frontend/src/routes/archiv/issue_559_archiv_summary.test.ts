// TDD RED — Issue #559: Archiv "Was passiert ist"-Spalte (AC-3) + Briefing-History-Button (AC-1).
// Spec: docs/specs/modules/issue_559_archiv_fertigstellen.md
//
// Die Implementierungen existieren noch nicht → Source-Inspection-Tests FEHLSCHLAGEN.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/routes/archiv/issue_559_archiv_summary.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const PAGE_FILE = join(here, '+page.svelte');
const HELPERS_FILE = join(here, 'archiveHelpers.ts');
const DIALOG_FILE = join(
	here,
	'..',
	'..',
	'lib',
	'components',
	'briefing-history',
	'BriefingHistoryDialog.svelte'
);

function readPage(): string {
	return readFileSync(PAGE_FILE, 'utf-8');
}
function readHelpers(): string {
	return readFileSync(HELPERS_FILE, 'utf-8');
}

// =============================================================================
// AC-3: "Was passiert ist"-Spalte zeigt Zusammenfassung statt hartem "—"
// =============================================================================

test('AC-3: "Was passiert ist"-Spalte verwendet archiveStats.briefings (nicht hartkodiertes —)', () => {
	const code = readPage();
	// Die Spalte darf nicht mehr einfach nur "—" rendern — sie muss auf archiveStats zugreifen
	assert.ok(
		/archiveStats\.briefings\[/.test(code) || /briefingCount\b/.test(code) || /eventSummary\b/.test(code),
		'"Was passiert ist"-Spalte muss archiveStats.briefings[] für die Zusammenfassung verwenden'
	);
});

test('AC-3: archiveHelpers.ts exportiert formatEventSummary-Funktion', () => {
	const code = readHelpers();
	assert.ok(
		/export\s+function\s+formatEventSummary/.test(code),
		'archiveHelpers.ts muss formatEventSummary() exportieren'
	);
});

test('AC-3: formatEventSummary("12 Briefings · 3 Alerts") bei briefings=12, alerts=3', () => {
	// Source-Inspection: Die Funktion muss den Trennpunkt "·" und "Alerts" referenzieren
	const code = readHelpers();
	const hasMiddot = /·/.test(code) || /\\u00B7/.test(code) || /'·'/.test(code) || /"·"/.test(code);
	assert.ok(
		hasMiddot,
		'formatEventSummary muss "·" als Trennzeichen zwischen Briefings und Alerts verwenden'
	);
});

test('AC-3: formatEventSummary zeigt nur "N Briefings" wenn alerts=0', () => {
	// Die Funktion muss alert=0 abfangen und weglassen
	const code = readHelpers();
	assert.ok(
		/alerts\s*[=!]==?\s*0|alerts\s*&&|!alerts/.test(code),
		'formatEventSummary muss Alerts=0 abfangen und den Alert-Teil weglassen'
	);
});

test('AC-3: formatEventSummary gibt "—" zurück wenn briefings=0 UND alerts=0', () => {
	const code = readHelpers();
	// Muss den Spezialfall 0+0 → "—" behandeln
	assert.ok(
		/briefings\s*[=!]==?\s*0|!briefings|briefings\s*</.test(code),
		'formatEventSummary muss briefings=0 als Sonderfall behandeln (→ "—")'
	);
});

// =============================================================================
// AC-1: BriefingHistoryDialog-Komponente existiert
// =============================================================================

test('AC-1: BriefingHistoryDialog.svelte existiert', () => {
	assert.ok(
		existsSync(DIALOG_FILE),
		`BriefingHistoryDialog.svelte fehlt unter: ${DIALOG_FILE}`
	);
});

test('AC-1: +page.svelte importiert BriefingHistoryDialog', () => {
	const code = readPage();
	assert.ok(
		/BriefingHistoryDialog/.test(code),
		'+page.svelte muss BriefingHistoryDialog importieren und verwenden'
	);
});

// =============================================================================
// AC-6: Keine Hex-Literale in +page.svelte (CSS-Token-Pflicht)
// =============================================================================

test('AC-6: +page.svelte enthält keine hardkodierten Hex-Farben in CSS-Properties', () => {
	const code = readPage();
	// Nur Hex-Werte in CSS-Kontext prüfen (color:, background:, fill: etc.) — nicht Issue-Nummern in Kommentaren
	const hexInStyle = /(?:color|background|fill|stroke|border)\s*[:=]\s*["']?#[0-9a-fA-F]{3,6}\b/g;
	const hexMatches = code.match(hexInStyle) ?? [];
	assert.strictEqual(
		hexMatches.length,
		0,
		`+page.svelte enthält Hex-Farben in CSS-Properties: ${hexMatches.join(', ')} — nur --g-* Tokens erlaubt`
	);
});
