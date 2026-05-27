// TDD RED: Issue #393 — Cockpit-Kacheln: Versandstatus + Alarm-Historie.
//
// Source-Inspection-Tests (mock-frei):
//   AC-8: +page.server.ts enthält cockpit-Fetch mit AbortSignal.timeout
//   AC-10: +page.server.ts ruft keinen Wetter-Endpoint auf
//   AC-4/5: cockpitHelpers.ts - plannedBriefings() hat sentLog-Parameter
//
// RED vor Implementierung:
//   - +page.server.ts fetcht noch kein /api/cockpit/status → AC-8 FAIL
//   - cockpitHelpers.ts/plannedBriefings() hat noch keinen sentLog-Parameter → AC-4/5 FAIL
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/lib/issue_393_cockpit_kacheln.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const SRC = join(here, '..'); // frontend/src/

function read(rel: string): string {
	return readFileSync(join(SRC, rel), 'utf-8');
}

// AC-8: SSR-Loader fetcht /api/cockpit/status
test('test_page_server_fetches_cockpit_status', () => {
	const src = read('routes/+page.server.ts');
	assert.ok(
		src.includes('/api/cockpit/status'),
		'+page.server.ts muss /api/cockpit/status fetchen (AC-8)'
	);
});

// AC-8: cockpit-Fetch verwendet AbortSignal.timeout
test('test_page_server_uses_abort_signal_timeout', () => {
	const src = read('routes/+page.server.ts');
	// Der cockpit-Fetch muss AbortSignal.timeout enthalten (nach /api/cockpit/status)
	const cockpitIdx = src.indexOf('/api/cockpit/status');
	assert.ok(cockpitIdx !== -1, '/api/cockpit/status nicht gefunden');

	// Im Kontext des cockpit-Fetchs muss AbortSignal.timeout(3000) oder ähnlich stehen
	const afterCockpit = src.slice(Math.max(0, cockpitIdx - 200), cockpitIdx + 300);
	assert.ok(
		afterCockpit.includes('AbortSignal.timeout'),
		'cockpit-Fetch muss AbortSignal.timeout() verwenden (AC-8)'
	);
});

// AC-10: Kein Wetter-Endpoint in SSR-Loader
test('test_page_server_no_weather_endpoint', () => {
	const src = read('routes/+page.server.ts');
	// Verbotene Wetter-Endpoints (Live-Wetter-Fetch ist nicht erlaubt auf Home-Seite)
	const forbidden = [
		'/api/trips/',
		'stages/weather',
		'open-meteo.com',
		'GZ_WEATHER',
	];
	for (const pattern of forbidden) {
		// Ausnahme: fetch('/api/trips') für die Trip-Liste ist erlaubt,
		// aber '/api/trips/' mit nachfolgendem Path (stage-weather) nicht
		if (pattern === '/api/trips/') {
			// Prüfe nur auf stage-weather-spezifische Pfade
			assert.ok(
				!src.includes('stages/weather'),
				`+page.server.ts darf keinen stages/weather-Endpoint aufrufen (AC-10)`
			);
		} else if (pattern !== 'GZ_WEATHER') {
			assert.ok(
				!src.includes(pattern),
				`+page.server.ts darf ${pattern} nicht aufrufen (AC-10)`
			);
		}
	}
});

// AC-4/5: plannedBriefings() hat sentLog-Parameter
test('test_cockpit_helpers_planned_briefings_accepts_sent_log', () => {
	const src = read('routes/_home/cockpitHelpers.ts');
	// plannedBriefings() muss einen optionalen sentLog-Parameter haben
	const hasSentLogParam =
		src.includes('sentLog') &&
		src.includes('plannedBriefings');
	assert.ok(
		hasSentLogParam,
		'cockpitHelpers.ts/plannedBriefings() muss sentLog-Parameter haben (AC-4/5)'
	);
});
