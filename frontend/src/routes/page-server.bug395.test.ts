// TDD RED: Bug #395 — SSR-Loader-Timeout fehlt auf Startseite (+page.server.ts).
//
// Spec: docs/specs/modules/bug_395_ssr_timeout.md
//
// Source-Inspection-Sentinel (mock-frei): Prüft, dass AbortSignal.timeout()
// in +page.server.ts gesetzt ist. Schlägt fehl, solange der Fix fehlt.
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/routes/page-server.bug395.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(__dirname, '+page.server.ts'), 'utf-8');

test('AC-1: Wetter-Fetch hat AbortSignal.timeout(3500)', () => {
	// GIVEN: +page.server.ts SSR-Loader
	// WHEN: der Source-Text gelesen wird
	// THEN: enthält der heroWeather-Fetch AbortSignal.timeout(3500)
	assert.ok(
		src.includes('AbortSignal.timeout(3500)'),
		'AbortSignal.timeout(3500) fehlt im Wetter-Fetch — Startseite kann bis zu 57s hängen'
	);
});

test('AC-2: trips/subscriptions-Fetches haben AbortSignal.timeout(5000) (mind. 2×)', () => {
	// GIVEN: +page.server.ts SSR-Loader
	// WHEN: der Source-Text gelesen wird
	// THEN: kommt AbortSignal.timeout(5000) mindestens 2× vor (trips + subscriptions)
	const matches = src.match(/AbortSignal\.timeout\(5000\)/g) ?? [];
	assert.ok(
		matches.length >= 2,
		`AbortSignal.timeout(5000) erwartet >=2× für trips+subscriptions, gefunden: ${matches.length}`
	);
});

test('AC-3: AbortSignal.timeout kommt insgesamt mindestens 3× vor', () => {
	// GIVEN: +page.server.ts SSR-Loader
	// WHEN: alle fetch()-Aufrufe gezählt werden
	// THEN: sind alle 3 Fetches (weather + trips + subscriptions) mit Timeout gesichert
	const matches = src.match(/AbortSignal\.timeout\(/g) ?? [];
	assert.ok(
		matches.length >= 3,
		`AbortSignal.timeout erwartet >=3×, gefunden: ${matches.length} — nicht alle Fetches sind abgesichert`
	);
});
