// TDD RED: Issue #189 — Preview-Tab-Integration: Pure-Function-Tests
//
// Spec: docs/specs/modules/issue_189_preview_tab_integration.md
// Master: docs/specs/modules/epic_140_output_vorschau.md
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/preview/__tests__/previewHelpers.test.ts
//
// Diese Tests decken AC-1 (Initial-Default), AC-6 (charCountStatus-Schwellen)
// und AC-7 (URL-Builder) ab. Die Komponenten-ACs (AC-2..AC-5, AC-8) werden
// in Phase 7 (Validation) per E2E-Hook gegen den laufenden Server verifiziert
// — gleiches Muster wie bei Issue #183 (headerStats.test.ts).

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
	buildPreviewUrl,
	defaultReportType,
	charCountStatus,
	friendlyPreviewError,
	PREVIEW_ERROR_GENERIC,
	PREVIEW_ERROR_NO_WAYPOINTS,
	type ReportType
} from '../previewHelpers.ts';

// ============================================================================
// AC-7: buildPreviewUrl — URL-Generierung
// ============================================================================

test('AC-7: buildPreviewUrl(email, gr20, morning) ohne date → kein date-Param', () => {
	assert.equal(
		buildPreviewUrl('email', 'gr20', 'morning'),
		'/api/preview/gr20/email?type=morning'
	);
});

test('AC-7: buildPreviewUrl(sms, gr20, evening, 2026-05-20) → date als Query', () => {
	assert.equal(
		buildPreviewUrl('sms', 'gr20', 'evening', '2026-05-20'),
		'/api/preview/gr20/sms?type=evening&date=2026-05-20'
	);
});

test('AC-7: buildPreviewUrl encodet trip_id mit Sonderzeichen', () => {
	assert.equal(
		buildPreviewUrl('email', 'tour/2026', 'morning'),
		'/api/preview/tour%2F2026/email?type=morning'
	);
});

test('AC-7: buildPreviewUrl unterscheidet zwischen email und sms Kanal', () => {
	assert.equal(
		buildPreviewUrl('email', 'x', 'morning'),
		'/api/preview/x/email?type=morning'
	);
	assert.equal(
		buildPreviewUrl('sms', 'x', 'morning'),
		'/api/preview/x/sms?type=morning'
	);
});

// ============================================================================
// AC-6 (Issue #363): buildPreviewUrl akzeptiert signal + telegram
// ============================================================================

test('AC-6: buildPreviewUrl(signal, gr20, morning) → signal-Endpoint', () => {
	assert.equal(
		buildPreviewUrl('signal', 'gr20', 'morning'),
		'/api/preview/gr20/signal?type=morning'
	);
});

test('AC-6: buildPreviewUrl(telegram, gr20, evening, 2026-05-25) → telegram + date', () => {
	assert.equal(
		buildPreviewUrl('telegram', 'gr20', 'evening', '2026-05-25'),
		'/api/preview/gr20/telegram?type=evening&date=2026-05-25'
	);
});

test('AC-6: buildPreviewUrl encodet trip_id auch für signal-Kanal', () => {
	assert.equal(
		buildPreviewUrl('signal', 'tour/2026', 'morning'),
		'/api/preview/tour%2F2026/signal?type=morning'
	);
});

// ============================================================================
// AC-1: defaultReportType — Initial-Default für Morning/Evening
// ============================================================================

test('AC-1: defaultReportType vor 14:00 lokal → morning', () => {
	const d = new Date('2026-05-16T10:00:00');
	assert.equal(defaultReportType(d), 'morning');
});

test('AC-1: defaultReportType genau 14:00 → evening (Grenze)', () => {
	const d = new Date('2026-05-16T14:00:00');
	assert.equal(defaultReportType(d), 'evening');
});

test('AC-1: defaultReportType nach 14:00 → evening', () => {
	const d = new Date('2026-05-16T18:30:00');
	assert.equal(defaultReportType(d), 'evening');
});

test('AC-1: defaultReportType ganz früh 00:30 → morning', () => {
	const d = new Date('2026-05-16T00:30:00');
	assert.equal(defaultReportType(d), 'morning');
});

// ============================================================================
// AC-6: charCountStatus — Schwellen ok / warn / over
// ============================================================================

test('AC-6: charCountStatus für ≤144 Zeichen → ok', () => {
	assert.equal(charCountStatus(0), 'ok');
	assert.equal(charCountStatus(100), 'ok');
	assert.equal(charCountStatus(144), 'ok');
});

test('AC-6: charCountStatus für 145..160 Zeichen → warn (Warn-Puffer)', () => {
	assert.equal(charCountStatus(145), 'warn');
	assert.equal(charCountStatus(150), 'warn');
	assert.equal(charCountStatus(160), 'warn');
});

test('AC-6: charCountStatus für ≥161 Zeichen → over (Limit überschritten)', () => {
	assert.equal(charCountStatus(161), 'over');
	assert.equal(charCountStatus(200), 'over');
	assert.equal(charCountStatus(500), 'over');
});

test('AC-6: charCountStatus respektiert custom limit', () => {
	// limit=80 → warn-Schwelle bei n > 64 (limit - 16), over bei n > 80
	assert.equal(charCountStatus(50, 80), 'ok');
	assert.equal(charCountStatus(64, 80), 'ok');
	assert.equal(charCountStatus(65, 80), 'warn');
	assert.equal(charCountStatus(80, 80), 'warn');
	assert.equal(charCountStatus(81, 80), 'over');
});

// ============================================================================
// Typ-Sanity: ReportType-Werte sind exakt das erwartete Literal-Paar
// ============================================================================

test('AC-1: ReportType-Type lässt nur morning|evening zu (Compile-Sanity)', () => {
	const morning: ReportType = 'morning';
	const evening: ReportType = 'evening';
	assert.equal(morning, 'morning');
	assert.equal(evening, 'evening');
});

// ============================================================================
// Issue #421 — friendlyPreviewError: technische Fehler → verständliches Deutsch
// ============================================================================

// AC-1: Leere Wegpunkte (422 + detail enthält "waypoint") → Wegpunkt-Hinweis
test('#421 AC-1: 422 mit waypoint-detail → PREVIEW_ERROR_NO_WAYPOINTS', () => {
	const body = '{"detail":"Stage must have at least one waypoint"}';
	assert.equal(friendlyPreviewError(422, body), PREVIEW_ERROR_NO_WAYPOINTS);
});

test('#421 AC-1: Wegpunkt-Meldung ist deutsch + actionable (Wegpunkt-Editor)', () => {
	assert.match(PREVIEW_ERROR_NO_WAYPOINTS, /Wegpunkte/);
	assert.match(PREVIEW_ERROR_NO_WAYPOINTS, /Wegpunkt-Editor/);
	// Kein englischer Rohtext durchgereicht
	assert.doesNotMatch(PREVIEW_ERROR_NO_WAYPOINTS, /waypoint/i);
});

// AC-2: Jeder andere Fehler → generische Meldung, OHNE HTTP-Zahl / JSON-Klammern
test('#421 AC-2: 503 weather-provider → PREVIEW_ERROR_GENERIC', () => {
	const body = '{"detail":"weather provider unavailable"}';
	assert.equal(friendlyPreviewError(503, body), PREVIEW_ERROR_GENERIC);
});

test('#421 AC-2: 404 trip-not-found → PREVIEW_ERROR_GENERIC', () => {
	assert.equal(
		friendlyPreviewError(404, '{"detail":"trip not found"}'),
		PREVIEW_ERROR_GENERIC
	);
});

test('#421 AC-2: 502 proxy-upstream → PREVIEW_ERROR_GENERIC', () => {
	assert.equal(
		friendlyPreviewError(502, '{"error":"upstream unreachable"}'),
		PREVIEW_ERROR_GENERIC
	);
});

test('#421 AC-2: generische Meldung enthält weder HTTP-Zahl noch JSON-Klammern', () => {
	const msg = friendlyPreviewError(503, '{"detail":"x"}');
	assert.ok(!msg.includes('{'), 'keine öffnende JSON-Klammer');
	assert.ok(!msg.includes('}'), 'keine schließende JSON-Klammer');
	assert.doesNotMatch(msg, /\d{3}/, 'keine 3-stellige HTTP-Statuszahl');
	assert.doesNotMatch(msg, /HTTP/i, 'kein "HTTP"-Präfix');
});

// AC-3: defensiv — wirft nie, Roh-String-Fallback, leerer/kaputter Body
test('#421 AC-3: leerer Body → generische Meldung, kein Throw', () => {
	assert.equal(friendlyPreviewError(500, ''), PREVIEW_ERROR_GENERIC);
});

test('#421 AC-3: nicht-JSON-Body wirft nicht → generische Meldung', () => {
	assert.equal(friendlyPreviewError(500, '<<<kaputt'), PREVIEW_ERROR_GENERIC);
});

test('#421 AC-3: waypoint als Roh-Plaintext (kein JSON) → Wegpunkt-Hinweis (Fallback)', () => {
	assert.equal(
		friendlyPreviewError(422, 'Stage must have at least one waypoint'),
		PREVIEW_ERROR_NO_WAYPOINTS
	);
});

test('#421 AC-3: detail als Array (FastAPI-Validierung) → generisch, kein Throw', () => {
	const body = '{"detail":[{"loc":["query","type"],"msg":"field required"}]}';
	assert.equal(friendlyPreviewError(422, body), PREVIEW_ERROR_GENERIC);
});

test('#421 AC-3: waypoint-Match ist case-insensitive', () => {
	assert.equal(
		friendlyPreviewError(422, '{"detail":"needs a WAYPOINT"}'),
		PREVIEW_ERROR_NO_WAYPOINTS
	);
});

// ============================================================================
// AC-4: Source-Inspection — kein roher Statuscode/JSON mehr in den Frames
// ============================================================================

const emailSrc = readFileSync(new URL('../EmailIframe.svelte', import.meta.url), 'utf8');
const smsSrc = readFileSync(new URL('../SmsPhoneFrame.svelte', import.meta.url), 'utf8');

for (const [name, src] of [
	['EmailIframe.svelte', emailSrc],
	['SmsPhoneFrame.svelte', smsSrc]
] as const) {
	test(`#421 AC-4: ${name} reicht keinen rohen HTTP-Status/Body mehr durch`, () => {
		assert.ok(!src.includes('HTTP ${res.status}'), 'keine rohe HTTP-Statuszahl');
		assert.ok(!src.includes('${detail}'), 'kein roher Body angehängt');
		assert.ok(!src.includes('Netzwerkfehler:'), 'kein rohes "Netzwerkfehler:"-Präfix');
	});

	test(`#421 AC-4: ${name} verwendet friendlyPreviewError`, () => {
		assert.ok(src.includes('friendlyPreviewError'), 'importiert + nutzt die zentrale Funktion');
	});

	test(`#421 AC-4: ${name} behält AbortError-Early-Return im catch-Zweig`, () => {
		assert.match(src, /AbortError/);
	});
}

// ============================================================================
// Issue #483: Demo-Modus — buildPreviewUrl mit demo-Parameter
// TDD RED: Diese Tests MÜSSEN FEHLSCHLAGEN bis die Implementierung existiert.
// buildPreviewUrl akzeptiert noch keinen 5. Parameter, demo=1 fehlt in der URL.
// ============================================================================

test('#483 AC-4: buildPreviewUrl mit demo=true hängt demo=1 an die URL', () => {
	const url = buildPreviewUrl('email', 'gr20', 'morning', undefined, true);
	assert.ok(
		url.includes('demo=1'),
		`URL muss demo=1 enthalten, war: ${url}`
	);
});

test('#483 AC-4: buildPreviewUrl mit demo=true und date enthält beide Parameter', () => {
	const url = buildPreviewUrl('sms', 'gr20', 'evening', '2026-06-10', true);
	assert.ok(url.includes('demo=1'), `URL muss demo=1 enthalten, war: ${url}`);
	assert.ok(url.includes('date=2026-06-10'), `URL muss date enthalten, war: ${url}`);
});

test('#483 AC-5: buildPreviewUrl ohne demo enthält keinen demo-Parameter', () => {
	const url = buildPreviewUrl('email', 'gr20', 'morning');
	assert.ok(
		!url.includes('demo'),
		`URL darf kein demo enthalten wenn nicht übergeben, war: ${url}`
	);
});

test('#483 AC-5: buildPreviewUrl mit demo=false hängt keinen demo-Param an', () => {
	const url = buildPreviewUrl('email', 'gr20', 'morning', undefined, false);
	assert.ok(
		!url.includes('demo'),
		`URL darf kein demo enthalten bei demo=false, war: ${url}`
	);
});
