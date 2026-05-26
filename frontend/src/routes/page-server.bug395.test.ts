// Bug #395 — SSR-Loader-Timeout auf Startseite (+page.server.ts).
//
// Spec: docs/specs/modules/bug_395_ssr_timeout.md
//
// Issue #395 — Loader holt KEIN Live-Wetter mehr; trips/subscriptions behalten
// defensive AbortSignal.timeout(5000), damit `/` bei langsamen Endpoints nicht
// haengt (fail-soft). Den "kein Live-Wetter"-Guard prueft separat
// frontend/src/lib/home-loader-no-weather.test.ts.
//
// Source-Inspection-Sentinel (mock-frei): Prüft, dass AbortSignal.timeout()
// auf den trips/subscriptions-Fetches in +page.server.ts gesetzt ist.
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

test('AC-3: AbortSignal.timeout kommt insgesamt mindestens 2× vor', () => {
	// GIVEN: +page.server.ts SSR-Loader
	// WHEN: alle fetch()-Aufrufe gezählt werden
	// THEN: sind beide Fetches (trips + subscriptions) mit Timeout gesichert.
	//   Kein Wetter-Fetch mehr (Issue #395), daher nur noch >=2× statt >=3×.
	const matches = src.match(/AbortSignal\.timeout\(/g) ?? [];
	assert.ok(
		matches.length >= 2,
		`AbortSignal.timeout erwartet >=2× für trips+subscriptions, gefunden: ${matches.length} — nicht alle Fetches sind abgesichert`
	);
});
