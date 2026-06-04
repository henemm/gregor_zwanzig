// TDD RED: Issue #588 — LocationNewModal 1:1 nach screen-location-new.jsx
//
// Spec: docs/specs/modules/issue_588_location_new.md
//
// Source-Inspection-Tests: lesen echte .svelte-Dateien und pruefen,
// dass LocationNewModal.svelte korrekt implementiert und in +page.svelte
// eingebunden ist.
//
// RED-Erwartung (vor Implementation):
//   - LocationNewModal.svelte existiert nicht → alle AC-1..AC-5 FAIL
//   - +page.svelte importiert LocationNewModal nicht → AC-1 FAIL
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/routes/locations/__tests__/issue_588_location_new_modal.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const FRONTEND = fileURLToPath(new URL('../../../../', import.meta.url)); // -> frontend/

const MODAL_PATH    = join(FRONTEND, 'src/lib/components/compare/LocationNewModal.svelte');
const PAGE_PATH     = join(FRONTEND, 'src/routes/locations/+page.svelte');

// ── AC-1: Vollflächiges Modal-Overlay, kein Shadcn-Dialog-Wrapper ─────────

test('AC-1: LocationNewModal.svelte existiert', () => {
	assert.ok(
		existsSync(MODAL_PATH),
		'frontend/src/lib/components/compare/LocationNewModal.svelte fehlt — muss neu erstellt werden'
	);
});

test('AC-1: +page.svelte importiert LocationNewModal', () => {
	const src = readFileSync(PAGE_PATH, 'utf-8');
	assert.match(
		src,
		/import\s+LocationNewModal\s+from\s+['"][^'"]*compare\/LocationNewModal[^'"]*['"]/,
		'+page.svelte muss LocationNewModal aus compare/LocationNewModal.svelte importieren'
	);
});

test('AC-1: LocationNewModal verwendet position:fixed fuer Overlay (kein Shadcn Dialog.Root)', () => {
	const src = readFileSync(MODAL_PATH, 'utf-8');
	assert.ok(
		src.includes('position:fixed') || src.includes('position: fixed'),
		'LocationNewModal muss ein position:fixed Overlay-Div verwenden (kein Shadcn Dialog-Wrapper)'
	);
	assert.doesNotMatch(
		src,
		/Dialog\.Root|from.*shadcn.*dialog/i,
		'LocationNewModal darf keinen Shadcn-Dialog-Wrapper verwenden'
	);
});

test('AC-1: Modal-Card hat 720px Breite', () => {
	const src = readFileSync(MODAL_PATH, 'utf-8');
	assert.ok(
		src.includes('720px') || src.includes('width:720') || src.includes('width: 720'),
		'Modal-Card muss 720px breit sein (per JSX-Spec)'
	);
});

test('AC-1: +page.svelte zeigt LocationNewModal wenn create-Modus aktiv', () => {
	const src = readFileSync(PAGE_PATH, 'utf-8');
	assert.match(
		src,
		/<LocationNewModal/,
		'+page.svelte muss <LocationNewModal> enthalten'
	);
});

// ── AC-2: Smart-Import ruft POST /api/locations/resolve auf ───────────────

test('AC-2: LocationNewModal enthaelt Aufruf von /api/locations/resolve', () => {
	const src = readFileSync(MODAL_PATH, 'utf-8');
	assert.ok(
		src.includes('/api/locations/resolve'),
		'LocationNewModal muss POST /api/locations/resolve aufrufen (Smart-Import)'
	);
});

test('AC-2: Vorschau-Grid zeigt KV-Eintraege nach Aufloesung', () => {
	const src = readFileSync(MODAL_PATH, 'utf-8');
	// Pruefen dass KV-Atom genutzt wird
	assert.ok(
		src.includes('<KV') || src.includes('{@render') && src.includes('KV'),
		'LocationNewModal muss <KV>-Eintraege fuer Vorschau-Grid (Quelle, Koordinaten, Hoehe, ...) enthalten'
	);
});

test('AC-2: Smart-Import-Feld und Format-Chips vorhanden', () => {
	const src = readFileSync(MODAL_PATH, 'utf-8');
	// Mindestens einen Format-Chip oder die Chip-Render-Logik pruefen
	assert.ok(
		src.includes('Komoot') && src.includes('Google Maps'),
		'LocationNewModal muss Format-Chips fuer Komoot-URL und Google-Maps zeigen'
	);
});

// ── AC-3: Speichern ruft POST /api/locations auf und feuert onsave ─────────

test('AC-3: LocationNewModal enthaelt Aufruf von /api/locations (ohne /resolve)', () => {
	const src = readFileSync(MODAL_PATH, 'utf-8');
	// Muss /api/locations enthalten, aber getrennt von /resolve
	assert.ok(
		src.includes('/api/locations'),
		'LocationNewModal muss POST /api/locations aufrufen (Ort speichern)'
	);
});

test('AC-3: LocationNewModal empfaengt onsave-Prop und ruft sie nach erfolgreichem Speichern auf', () => {
	const src = readFileSync(MODAL_PATH, 'utf-8');
	assert.match(
		src,
		/onsave\s*[:(]/,
		'LocationNewModal muss eine onsave-Prop empfangen und nach erfolgreichem Speichern aufrufen'
	);
});

test('AC-3: Speichern-Button ist vorhanden und an Speichern-Funktion gebunden', () => {
	const src = readFileSync(MODAL_PATH, 'utf-8');
	assert.ok(
		src.includes('Ort speichern'),
		'LocationNewModal muss Button mit Text "Ort speichern" enthalten'
	);
});

// ── AC-4: Abbrechen und Schliessen-Button feuern oncancel ─────────────────

test('AC-4: LocationNewModal empfaengt oncancel-Prop', () => {
	const src = readFileSync(MODAL_PATH, 'utf-8');
	assert.match(
		src,
		/oncancel\s*[:(]/,
		'LocationNewModal muss eine oncancel-Prop empfangen'
	);
});

test('AC-4: Abbrechen-Button und Schliessen-Button (×) sind vorhanden', () => {
	const src = readFileSync(MODAL_PATH, 'utf-8');
	assert.ok(
		src.includes('Abbrechen'),
		'LocationNewModal muss Button mit Text "Abbrechen" enthalten'
	);
	assert.ok(
		src.includes('×') || src.includes('&times;') || src.includes('aria-label') && src.includes('chließen'),
		'LocationNewModal muss einen Schliessen-Button (×) enthalten'
	);
});

// ── AC-5: Aktivitaetsprofil-Auswahl mit Akzent-Hervorhebung ───────────────

test('AC-5: LocationNewModal rendert Aktivitaetsprofil-Karten fuer alle Profile', () => {
	const src = readFileSync(MODAL_PATH, 'utf-8');
	// ACTIVITY_PROFILE_OPTIONS muss importiert oder die Profile direkt referenziert sein
	assert.ok(
		src.includes('ACTIVITY_PROFILE_OPTIONS') || src.includes('activity_profile') || src.includes('wandern'),
		'LocationNewModal muss Aktivitaetsprofil-Karten rendern (alle 4 Profile aus ACTIVITY_PROFILE_OPTIONS)'
	);
});

test('AC-5: Aktive Profil-Karte bekommt Akzent-Border und Akzent-Tint-Hintergrund', () => {
	const src = readFileSync(MODAL_PATH, 'utf-8');
	assert.ok(
		src.includes('g-accent') || src.includes('var(--g-accent'),
		'LocationNewModal muss var(--g-accent) fuer die aktive Karte nutzen (Akzent-Border/Tint)'
	);
});

test('AC-5: Sektion 3 hat nummerierte Ueberschrift "Meteorologische Brille"', () => {
	const src = readFileSync(MODAL_PATH, 'utf-8');
	assert.ok(
		src.includes('Meteorologische Brille') || src.includes('Aktivitätsprofil'),
		'LocationNewModal muss Sektion 3 "Meteorologische Brille" enthalten'
	);
});

// ── Zusatz: Design-Token-Konformitaet ─────────────────────────────────────

test('Design-Tokens: LocationNewModal nutzt nur var(--g-*) — kein rohes Hex', () => {
	const src = readFileSync(MODAL_PATH, 'utf-8');
	// Pruefen auf rohes Hex (6-stellig) ausserhalb von Kommentaren
	const noComments = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*/g, '');
	const hexMatches = noComments.match(/#[0-9a-fA-F]{6}\b/g) ?? [];
	assert.strictEqual(
		hexMatches.length,
		0,
		`LocationNewModal darf keine rohen Hex-Farben enthalten — gefunden: ${hexMatches.join(', ')} (nur var(--g-*) erlaubt)`
	);
});

test('Design-Tokens: LocationNewModal importiert Atoms aus $lib/components/atoms', () => {
	const src = readFileSync(MODAL_PATH, 'utf-8');
	assert.match(
		src,
		/from\s+['"][^'"]*components\/atoms[^'"]*['"]/,
		'LocationNewModal muss Atoms aus $lib/components/atoms importieren (Eyebrow, Pill, KV, TopoBg, Btn)'
	);
});
