// TDD RED: Bug #595 + #597 — reset-password UX + /weather löschen
//
// Spec: docs/specs/modules/bug_595_597_auth_weather.md
//
// Source-Inspection-Tests: lesen echte .svelte-Quelldateien.
// Kein Browser, keine Mocks.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/routes/__tests__/bug_595_597_auth_weather.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const SRC = fileURLToPath(new URL('../..', import.meta.url)); // -> frontend/src/

function read(rel: string): string {
	return readFileSync(join(SRC, rel), 'utf8');
}

// --- #595 AC-1: Wordmark auf /reset-password ---

test('AC-1: /reset-password bindet Wordmark-Komponente ein', () => {
	const src = read('routes/reset-password/+page.svelte');
	assert.ok(
		src.includes('<Wordmark'),
		'/reset-password muss <Wordmark einbinden — analog zu /login'
	);
});

// --- #595 AC-2: Token-Feld versteckt wenn data.token gesetzt ---

test('AC-2: Token-Feld ist hidden wenn data.token gesetzt (URL-Parameter)', () => {
	const src = read('routes/reset-password/+page.svelte');
	// Muss eine Bedingung enthalten: wenn token vorhanden → type="hidden"
	assert.ok(
		src.includes('type="hidden"'),
		'Token-Input muss type="hidden" enthalten für den auto-fill-Fall (?token=...)'
	);
});

// --- #595 AC-3: Token-Feld sichtbar wenn kein URL-Token ---

test('AC-3: Token-Feld bleibt type="text" für manuelle Eingabe ohne URL-Token', () => {
	const src = read('routes/reset-password/+page.svelte');
	// Braucht BEIDE Zweige: hidden UND text/sichtbar
	const hasHidden = src.includes('type="hidden"');
	const hasVisible =
		src.includes('type="text"') ||
		// Placeholder "Reset-Token" zeigt sichtbares Feld
		src.includes('placeholder="Reset-Token"') ||
		src.includes('placeholder=');
	assert.ok(
		hasHidden && hasVisible,
		'Token-Feld braucht zwei Zweige: type="hidden" (URL-Token) und sichtbares Feld (manuelle Eingabe)'
	);
});

// --- #595 AC-4: Wordmark auf /forgot-password ---

test('AC-4: /forgot-password bindet Wordmark-Komponente ein', () => {
	const src = read('routes/forgot-password/+page.svelte');
	assert.ok(
		src.includes('<Wordmark'),
		'/forgot-password muss <Wordmark einbinden — Konsistenz mit /login und /reset-password'
	);
});

// --- #597 AC-5: /weather-Dateien gelöscht ---

test('AC-5: /weather/+page.svelte existiert nicht mehr', () => {
	const path = join(SRC, 'routes/weather/+page.svelte');
	assert.ok(
		!existsSync(path),
		'/weather/+page.svelte muss gelöscht sein (Route nicht mehr benötigt, war dead code)'
	);
});

test('AC-5b: /weather/+page.server.ts existiert nicht mehr', () => {
	const path = join(SRC, 'routes/weather/+page.server.ts');
	assert.ok(
		!existsSync(path),
		'/weather/+page.server.ts muss gelöscht sein (301-Redirect zu /compare entfernen)'
	);
});
