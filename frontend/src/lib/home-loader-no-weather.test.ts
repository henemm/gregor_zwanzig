// TDD RED: Issue #395 — Home-Loader holt kein Live-Wetter (Guard-Test)
//
// Spec: docs/specs/modules/home_weather_fetch_timeout.md
//
// Source-Inspection-Test (Pattern wie contrast-audit.test.ts / trip-terminology.test.ts):
// liest die echte +page.server.ts-Quelldatei als String und prueft, dass der
// Home-Loader KEINEN Live-Wetter-Abruf mehr enthaelt. PO-Direktive (#395):
// Die Website zeigt KEIN Live-Wetter — der SSR-Loader darf den Wetter-Endpoint
// (.../stages/weather) NICHT aufrufen, sonst haengt `/` bis ~57 s (Regression aus #386).
//
// Geprueft (AC-1, lasting Guard):
//   - kein Fetch/String auf `…/stages/weather`,
//   - kein `StagesWeatherResponse`-Import im Loader,
//   - kein `heroWeather`-Bezeichner (Live-Wetter-Variable) im Loader.
//
// RED: Vor dem Entfernen enthaelt +page.server.ts den stages/weather-Fetch,
//   den StagesWeatherResponse-Import und die heroWeather-Variable -> alle drei FAIL.
//   GREEN: nach dem Entfernen sind alle drei weg.
//
// Ausfuehrung:
//   cd frontend && node --test --experimental-strip-types src/lib/home-loader-no-weather.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const LOADER = fileURLToPath(new URL('../routes/+page.server.ts', import.meta.url));
const source = readFileSync(LOADER, 'utf-8');

test('AC-1: Home-Loader ruft den Wetter-Endpoint (stages/weather) nicht auf', () => {
	const re = /stages\/weather/;
	assert.ok(
		!re.test(source),
		'+page.server.ts enthaelt noch einen Verweis auf `stages/weather` — der SSR-Loader darf KEIN Live-Wetter holen (Issue #395, sonst haengt `/` bis ~57 s).'
	);
});

test('AC-1: Home-Loader importiert kein StagesWeatherResponse', () => {
	assert.ok(
		!/StagesWeatherResponse/.test(source),
		'+page.server.ts importiert/verwendet noch `StagesWeatherResponse` — der Loader hat keine Wetter-Abhaengigkeit mehr (Issue #395).'
	);
});

test('AC-1: Home-Loader holt kein heroWeather live', () => {
	assert.ok(
		!/heroWeather/.test(source),
		'+page.server.ts enthaelt noch die `heroWeather`-Variable (Live-Wetter) — entfernen (Issue #395).'
	);
});
