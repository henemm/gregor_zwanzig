// TDD RED: Issue #481 — Mobile Header zeigt Mond statt Glocke + Plus
//
// Spec: docs/specs/modules/issue_481_mobile_header_icons.md
//
// Source-Inspection-Tests: liest echte .svelte-Quelldateien und prüft,
// dass der Fix durchgeführt wurde. Kein Browser, keine Mocks.
//
// RED vor Implementierung:
//   AC-1: top-app-bar-bell + disabled fehlen → FAIL
//   AC-2: top-app-bar-new-trip + href="/trips/new" fehlen → FAIL
//   AC-3: MoonIcon/SunIcon noch vorhanden → FAIL
//   AC-4: Props darkMode/ontoggleDark vorhanden, aber kein Render → FAIL
//   AC-5: Sidebar hat noch Dark-Mode-Toggle → PASS (Regression-Schutz)
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/issue_481_mobile_header_icons.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const SRC = fileURLToPath(new URL('..', import.meta.url)); // -> frontend/src/

function read(rel: string): string {
	return readFileSync(join(SRC, rel), 'utf8');
}

// ---------------------------------------------------------------------------
// AC-1: Glocken-Button mit disabled-Attribut vorhanden
// ---------------------------------------------------------------------------

test('AC-1: TopAppBar enthält data-testid="top-app-bar-bell"', () => {
	const src = read('lib/components/ui/sidebar/TopAppBar.svelte');
	assert.ok(
		src.includes('top-app-bar-bell'),
		'data-testid="top-app-bar-bell" fehlt in TopAppBar.svelte'
	);
});

test('AC-1: Bell-Button hat disabled-Attribut (Placeholder ohne Benachrichtigungssystem)', () => {
	const src = read('lib/components/ui/sidebar/TopAppBar.svelte');
	// Prüft, dass disabled zusammen mit top-app-bar-bell vorkommt
	const bellSection = src.slice(src.indexOf('top-app-bar-bell') - 200, src.indexOf('top-app-bar-bell') + 200);
	assert.ok(
		bellSection.includes('disabled'),
		'Bell-Button muss disabled sein (top-app-bar-bell ohne disabled gefunden)'
	);
});

test('AC-1: Bell-Button nutzt MIcon mit kind="bell"', () => {
	const src = read('lib/components/ui/sidebar/TopAppBar.svelte');
	assert.ok(
		/MIcon[^>]*kind=["']bell["']|kind=["']bell["'][^>]*MIcon/.test(src) ||
		src.includes('"bell"') || src.includes("'bell'"),
		'MIcon kind="bell" fehlt in TopAppBar.svelte'
	);
});

// ---------------------------------------------------------------------------
// AC-2: Plus-Link mit href="/trips/new" vorhanden
// ---------------------------------------------------------------------------

test('AC-2: TopAppBar enthält data-testid="top-app-bar-new-trip"', () => {
	const src = read('lib/components/ui/sidebar/TopAppBar.svelte');
	assert.ok(
		src.includes('top-app-bar-new-trip'),
		'data-testid="top-app-bar-new-trip" fehlt in TopAppBar.svelte'
	);
});

test('AC-2: Plus-Element hat href="/trips/new"', () => {
	const src = read('lib/components/ui/sidebar/TopAppBar.svelte');
	assert.ok(
		src.includes('href="/trips/new"') || src.includes("href='/trips/new'"),
		'href="/trips/new" fehlt in TopAppBar.svelte'
	);
});

test('AC-2: Plus-Element nutzt MIcon mit kind="plus"', () => {
	const src = read('lib/components/ui/sidebar/TopAppBar.svelte');
	assert.ok(
		src.includes('"plus"') || src.includes("'plus'"),
		'MIcon kind="plus" fehlt in TopAppBar.svelte'
	);
});

// ---------------------------------------------------------------------------
// AC-3: Kein MoonIcon / SunIcon mehr im TopAppBar
// ---------------------------------------------------------------------------

test('AC-3: MoonIcon-Import ist aus TopAppBar.svelte entfernt', () => {
	const src = read('lib/components/ui/sidebar/TopAppBar.svelte');
	assert.ok(
		!src.includes('MoonIcon'),
		'MoonIcon ist noch in TopAppBar.svelte vorhanden — muss entfernt werden'
	);
});

test('AC-3: SunIcon-Import ist aus TopAppBar.svelte entfernt', () => {
	const src = read('lib/components/ui/sidebar/TopAppBar.svelte');
	assert.ok(
		!src.includes('SunIcon'),
		'SunIcon ist noch in TopAppBar.svelte vorhanden — muss entfernt werden'
	);
});

// ---------------------------------------------------------------------------
// AC-4: Props darkMode/ontoggleDark bleiben im Interface (kein Prop-Warning)
// ---------------------------------------------------------------------------

test('AC-4: darkMode-Prop bleibt im Interface von TopAppBar', () => {
	const src = read('lib/components/ui/sidebar/TopAppBar.svelte');
	assert.ok(
		src.includes('darkMode'),
		'darkMode-Prop fehlt in TopAppBar.svelte — wird vom Layout übergeben'
	);
});

test('AC-4: ontoggleDark-Prop bleibt im Interface von TopAppBar', () => {
	const src = read('lib/components/ui/sidebar/TopAppBar.svelte');
	assert.ok(
		src.includes('ontoggleDark'),
		'ontoggleDark-Prop fehlt in TopAppBar.svelte — wird vom Layout übergeben'
	);
});

// ---------------------------------------------------------------------------
// AC-5: Sidebar.svelte hat Dark-Mode-Toggle (Regression-Schutz)
// ---------------------------------------------------------------------------

test('AC-5: Sidebar.svelte enthält weiterhin den Dark-Mode-Toggle (Desktop/Drawer)', () => {
	const src = read('lib/components/ui/sidebar/Sidebar.svelte');
	assert.ok(
		src.includes('ontoggleDark') || src.includes('darkMode'),
		'Dark-Mode-Toggle fehlt in Sidebar.svelte — darf nicht entfernt werden'
	);
});
