// TDD: Issue #850 — Alerts-Tab: alert_rules werden nach Wetter-Metriken-Speichern korrekt gelesen
//
// AC-1: WeatherMetricsTab nutzt Server-Response für onTripUpdate
//   → PUT /api/trips/{id} gibt vollen Trip zurück; alert_rules aus SyncAlertRules enthalten.
//   → onTripUpdate erhält diesen Trip (nicht manuell konstruierten Payload ohne alert_rules).
//
// AC-2: AlertPreviewCard — Link auf Wetter-Metriken-Tab
//   → Hinweistext enthält Element data-testid="alert-preview-no-metrics-link" → href="?tab=weather"
//
// Execution:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/alerts-tab/issue_850_alert_metrics_stale.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ---------------------------------------------------------------------------
// AC-1: WeatherMetricsTab darf alert_rules NICHT aus lokalem trip-State bauen
// # doc-compliance-test
// ---------------------------------------------------------------------------

test('AC-1: WeatherMetricsTab nutzt PUT-Response, nicht manuell konstruierten Payload', () => {
	const src = readFileSync(
		join(__dirname, '../shared/WeatherMetricsTab.svelte'),
		'utf-8'
	);
	const antiPattern = 'onTripUpdate?.({ ...trip, display_config: payload, report_config: reportConfig })';
	assert.ok(
		!src.includes(antiPattern),
		'WeatherMetricsTab.svelte darf alert_rules NICHT manuell konstruieren — Server-Response nutzen (Issue #850)'
	);
});

test('AC-1: WeatherMetricsTab nutzt api.put<Trip> Rückgabewert für onTripUpdate', () => {
	const src = readFileSync(
		join(__dirname, '../shared/WeatherMetricsTab.svelte'),
		'utf-8'
	);
	assert.ok(
		src.includes('api.put<Trip>'),
		'WeatherMetricsTab.svelte muss api.put<Trip> verwenden (Issue #850)'
	);
	assert.ok(
		src.includes('onTripUpdate?.(updated)'),
		'WeatherMetricsTab.svelte muss onTripUpdate(updated) mit Server-Response aufrufen (Issue #850)'
	);
});

// ---------------------------------------------------------------------------
// AC-2: AlertPreviewCard enthält Link auf Wetter-Metriken-Tab
// # doc-compliance-test
// ---------------------------------------------------------------------------

test('AC-2: AlertPreviewCard Hinweistext enthält Link data-testid="alert-preview-no-metrics-link"', () => {
	const src = readFileSync(
		join(__dirname, 'AlertPreviewCard.svelte'),
		'utf-8'
	);
	assert.ok(
		src.includes('data-testid="alert-preview-no-metrics-link"'),
		'AlertPreviewCard.svelte muss Link mit data-testid="alert-preview-no-metrics-link" enthalten (Issue #850 AC-2)'
	);
	assert.ok(
		src.includes('href="?tab=weather"'),
		'AlertPreviewCard.svelte Link muss auf ?tab=weather verlinken (Issue #850 AC-2)'
	);
});
