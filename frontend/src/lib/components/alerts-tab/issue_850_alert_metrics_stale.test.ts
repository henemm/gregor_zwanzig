// TDD: Issue #850 — Alerts-Tab: alert_rules werden nach Wetter-Metriken-Speichern korrekt gelesen
//
// AC-1: WeatherMetricsTab nutzt Server-Response für onTripUpdate
//   → PUT /api/trips/{id} gibt vollen Trip zurück; alert_rules aus SyncAlertRules enthalten.
//   → onTripUpdate erhält diesen Trip (nicht manuell konstruierten Payload ohne alert_rules).
//
// AC-2: AlertPreviewCard — Link auf Wetter-Metriken-Tab
//   → Hinweistext enthält Element data-testid="alert-preview-no-metrics-link" → href="?tab=wetter-metriken"
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

// #3297/#3020: die Faelle gegen WeatherMetricsTab entfallen — Datei geloescht.


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
	// #2794 S3a: die Metrik-Auswahl liegt im Reiter Wetter.
	assert.ok(
		src.includes('href="?tab=wetter"'),
		'AlertPreviewCard.svelte Link muss auf ?tab=wetter verlinken (Issue #850 AC-2, #2794)'
	);
});
